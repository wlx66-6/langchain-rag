import axios, { type AxiosRequestConfig, type AxiosResponse } from 'axios'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, authApi, chatApi, clearTokens, getAccessToken, knowledgeApi, setTokens } from './api'

const originalAdapter = api.defaults.adapter

/** 用一个假的 adapter 顶替真实网络请求，从而在不联网的情况下跑通拦截器链路。 */
function stubAdapter(
  handler: (config: AxiosRequestConfig) => AxiosResponse | Promise<AxiosResponse>,
) {
  api.defaults.adapter = async (config) => handler(config)
}

function ok(config: AxiosRequestConfig, data: unknown = {}): AxiosResponse {
  return { data, status: 200, statusText: 'OK', headers: {}, config: config as never }
}

function unauthorized(config: AxiosRequestConfig): never {
  const err = new Error('Request failed with status code 401') as Error & Record<string, unknown>
  err.config = config
  err.response = { data: {}, status: 401, statusText: 'Unauthorized', headers: {}, config }
  throw err
}

afterEach(() => {
  api.defaults.adapter = originalAdapter
  vi.restoreAllMocks()
})

describe('令牌存取', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('初始时没有令牌', () => {
    expect(getAccessToken()).toBeNull()
  })

  it('setTokens 后能取到 access_token，refresh_token 也写入', () => {
    setTokens('access-abc', 'refresh-xyz')
    expect(getAccessToken()).toBe('access-abc')
    expect(localStorage.getItem('refresh_token')).toBe('refresh-xyz')
  })

  it('clearTokens 清空令牌和用户信息', () => {
    setTokens('access-abc', 'refresh-xyz')
    localStorage.setItem('user', '{"id":1}')
    clearTokens()
    expect(getAccessToken()).toBeNull()
    expect(localStorage.getItem('refresh_token')).toBeNull()
    expect(localStorage.getItem('user')).toBeNull()
  })
})

describe('请求拦截器', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('有令牌时自动带上 Authorization 头', async () => {
    setTokens('token-abc', 'refresh-xyz')
    let seen: AxiosRequestConfig | undefined
    stubAdapter((config) => {
      seen = config
      return ok(config)
    })

    await authApi.me()
    expect(seen?.headers?.Authorization).toBe('Bearer token-abc')
  })

  it('没有令牌时不带 Authorization 头', async () => {
    let seen: AxiosRequestConfig | undefined
    stubAdapter((config) => {
      seen = config
      return ok(config)
    })

    await authApi.login('alice', 'secret')
    expect(seen?.headers?.Authorization).toBeUndefined()
  })
})

describe('接口封装', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('authApi.login 打到正确地址并只返回 data', async () => {
    let seen: AxiosRequestConfig | undefined
    stubAdapter((config) => {
      seen = config
      return ok(config, { access_token: 'a', refresh_token: 'b' })
    })

    const data = await authApi.login('alice', 'secret')
    expect(seen?.url).toBe('/auth/login')
    expect(seen?.method).toBe('post')
    expect(data).toEqual({ access_token: 'a', refresh_token: 'b' })
  })

  it('chatApi.getMessages 打到会话消息地址', async () => {
    let seen: AxiosRequestConfig | undefined
    stubAdapter((config) => {
      seen = config
      return ok(config, [])
    })

    await chatApi.getMessages(42)
    expect(seen?.url).toBe('/conversations/42/messages')
  })

  it('chatApi.deleteConversation 使用 DELETE 方法', async () => {
    let seen: AxiosRequestConfig | undefined
    stubAdapter((config) => {
      seen = config
      return ok(config, {})
    })

    await chatApi.deleteConversation(7)
    expect(seen?.url).toBe('/conversations/7')
    expect(seen?.method).toBe('delete')
  })

  it('knowledgeApi.uploadDocument 以 FormData 形式提交文件', async () => {
    let seen: AxiosRequestConfig | undefined
    stubAdapter((config) => {
      seen = config
      return ok(config, { id: 1 })
    })

    const file = new File(['内容'], '商品.txt', { type: 'text/plain' })
    await knowledgeApi.uploadDocument(file)

    expect(seen?.url).toBe('/knowledge/upload')
    expect(seen?.data).toBeInstanceOf(FormData)
    expect((seen?.data as FormData).get('file')).toBe(file)
  })
})

describe('401 自动刷新令牌', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('用 refresh_token 换新令牌后重试原请求', async () => {
    setTokens('old-access', 'refresh-old')
    vi.spyOn(axios, 'post').mockResolvedValue({
      data: { access_token: 'new-access', refresh_token: 'refresh-new' },
    } as AxiosResponse)

    let attempt = 0
    stubAdapter((config) => {
      attempt += 1
      if (attempt === 1) unauthorized(config)
      return ok(config, { username: 'alice' })
    })

    const data = await authApi.me()

    expect(data).toEqual({ username: 'alice' })
    expect(attempt).toBe(2) // 第一次 401，刷新后重试成功
    expect(localStorage.getItem('access_token')).toBe('new-access')
  })

  it('刷新失败时清空令牌', async () => {
    setTokens('old-access', 'refresh-old')
    vi.spyOn(axios, 'post').mockRejectedValue(new Error('refresh failed'))
    stubAdapter((config) => unauthorized(config))

    await expect(authApi.me()).rejects.toBeTruthy()
    expect(getAccessToken()).toBeNull()
  })
})
