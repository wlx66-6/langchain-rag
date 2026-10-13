import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ChatPage from './ChatPage'
import { chatApi, getAccessToken, refreshAccessToken } from '../lib/api'
import { useAuth } from '../lib/auth'
import { renderWithProviders } from '../test/render'

vi.mock('../lib/api', () => ({
  chatApi: {
    listConversations: vi.fn(),
    getMessages: vi.fn(),
    deleteConversation: vi.fn(),
    createConversation: vi.fn(),
    renameConversation: vi.fn(),
  },
  getAccessToken: vi.fn(),
  refreshAccessToken: vi.fn(),
}))
vi.mock('../lib/auth', () => ({ useAuth: vi.fn() }))

const mockedChatApi = vi.mocked(chatApi)
const mockedUseAuth = vi.mocked(useAuth)
const mockedGetAccessToken = vi.mocked(getAccessToken)
const mockedRefresh = vi.mocked(refreshAccessToken)

/** 把若干 SSE 事件拼成一个流式 Response，模拟后端 /api/chat 的返回。 */
function sseResponse(events: object[], status = 200): Response {
  const encoder = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const e of events) {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(e)}\n\n`))
      }
      controller.close()
    },
  })
  return new Response(body, { status, headers: { 'Content-Type': 'text/event-stream' } })
}

const START_EVENT = {
  type: 'start',
  data: { conversation_id: 7, sources: [{ source: '商品说明.txt', content: '续航 40 小时' }] },
}

function renderPage() {
  return renderWithProviders(<ChatPage />)
}

async function ask(question: string) {
  fireEvent.change(screen.getByRole('textbox'), { target: { value: question } })
  fireEvent.click(screen.getByRole('button', { name: '发送' }))
}

beforeEach(() => {
  vi.clearAllMocks()
  mockedUseAuth.mockReturnValue({
    user: { id: 1, username: 'alice', is_admin: false },
    isAdmin: false,
    loading: false,
    login: vi.fn(),
    logout: vi.fn(),
  })
  mockedGetAccessToken.mockReturnValue('token-abc')
  mockedChatApi.listConversations.mockResolvedValue([])
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('ChatPage 挂载', () => {
  it('初始展示欢迎空态', async () => {
    renderPage()
    expect(await screen.findByText('欢迎使用知识库问答')).toBeTruthy()
  })

  it('挂载时拉取会话列表并渲染', async () => {
    mockedChatApi.listConversations.mockResolvedValue([
      { id: 1, title: '会话一', updated_at: '2026-01-01' },
      { id: 2, title: '会话二', updated_at: '2026-01-02' },
    ])
    renderPage()
    expect(await screen.findByText('会话一')).toBeTruthy()
    expect(screen.getByText('会话二')).toBeTruthy()
  })

  it('会话列表加载失败时用 toast 提示', async () => {
    mockedChatApi.listConversations.mockRejectedValue(new Error('后端没起来'))
    renderPage()
    expect(await screen.findByText('后端没起来')).toBeTruthy()
  })
})

describe('ChatPage 流式问答', () => {
  it('发送问题后流式拼接回答并展示引用', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        sseResponse([
          START_EVENT,
          { type: 'token', data: '你好' },
          { type: 'token', data: '，这是' },
          { type: 'token', data: '回答。' },
          { type: 'done' },
        ]),
      ),
    )
    renderPage()
    await screen.findByText('欢迎使用知识库问答')

    await ask('耳机续航多久？')

    expect(await screen.findByText('你好，这是回答。')).toBeTruthy()
    expect(screen.getByText('📄 商品说明.txt')).toBeTruthy()
    // 用户提问也出现在列表里
    expect(screen.getByText('耳机续航多久？')).toBeTruthy()
  })

  it('发送时带上 Authorization 头，并采用服务端返回的会话 ID', async () => {
    const fetchMock = vi.fn().mockResolvedValue(sseResponse([START_EVENT, { type: 'done' }]))
    vi.stubGlobal('fetch', fetchMock)
    renderPage()
    await screen.findByText('欢迎使用知识库问答')

    await ask('问题')

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/chat')
    expect((init as RequestInit).headers).toMatchObject({ Authorization: 'Bearer token-abc' })
    // 新建会话后，事件里的 conversation_id 被记录下来（侧栏刷新）
    await waitFor(() => expect(mockedChatApi.listConversations).toHaveBeenCalledTimes(2))
  })

  it('服务端返回 error 事件时用 toast 提示', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(sseResponse([START_EVENT, { type: 'error', data: '模型炸了' }])),
    )
    renderPage()
    await screen.findByText('欢迎使用知识库问答')

    await ask('会失败的问题')

    expect(await screen.findByText('模型炸了')).toBeTruthy()
  })

  it('401 时先刷新令牌再重试，不直接跳登录', async () => {
    mockedRefresh.mockResolvedValue('fresh-token')
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response('', { status: 401 }))
      .mockResolvedValueOnce(sseResponse([START_EVENT, { type: 'token', data: '好的' }, { type: 'done' }]))
    vi.stubGlobal('fetch', fetchMock)
    renderPage()
    await screen.findByText('欢迎使用知识库问答')

    await ask('问题')

    expect(await screen.findByText('好的')).toBeTruthy()
    expect(mockedRefresh).toHaveBeenCalled()
    const retryHeaders = (fetchMock.mock.calls[1][1] as RequestInit).headers
    expect(retryHeaders).toMatchObject({ Authorization: 'Bearer fresh-token' })
  })

  it('回答为空时不发送空请求', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderPage()
    await screen.findByText('欢迎使用知识库问答')

    fireEvent.click(screen.getByRole('button', { name: '发送' }))
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

describe('ChatPage 会话切换', () => {
  it('切换会话时加载历史消息与引用', async () => {
    mockedChatApi.listConversations.mockResolvedValue([
      { id: 3, title: '历史会话', updated_at: '2026-01-01' },
    ])
    mockedChatApi.getMessages.mockResolvedValue([
      { id: 1, role: 'user', content: '之前的问题', citations: null, created_at: '' },
      {
        id: 2,
        role: 'assistant',
        content: '之前的回答',
        citations: JSON.stringify([{ source: '旧文档.txt', content: '旧内容' }]),
        created_at: '',
      },
    ])
    renderPage()

    fireEvent.click(await screen.findByText('历史会话'))

    expect(await screen.findByText('之前的问题')).toBeTruthy()
    expect(screen.getByText('之前的回答')).toBeTruthy()
    expect(screen.getByText('📄 旧文档.txt')).toBeTruthy()
  })

  it('点击「新建」清空当前消息', async () => {
    mockedChatApi.listConversations.mockResolvedValue([
      { id: 3, title: '历史会话', updated_at: '2026-01-01' },
    ])
    mockedChatApi.getMessages.mockResolvedValue([
      { id: 1, role: 'user', content: '之前的问题', citations: null, created_at: '' },
    ])
    renderPage()

    fireEvent.click(await screen.findByText('历史会话'))
    await screen.findByText('之前的问题')

    fireEvent.click(screen.getByRole('button', { name: '＋ 新建' }))

    await waitFor(() => expect(screen.queryByText('之前的问题')).toBeNull())
    expect(screen.getByText('欢迎使用知识库问答')).toBeTruthy()
  })

  it('确认删除会话后调用删除接口', async () => {
    mockedChatApi.listConversations.mockResolvedValue([
      { id: 5, title: '待删除会话', updated_at: '2026-01-01' },
    ])
    mockedChatApi.deleteConversation.mockResolvedValue({})
    renderPage()

    fireEvent.click(await screen.findByText('待删除会话'))
    fireEvent.click(screen.getByRole('button', { name: '删除会话 待删除会话' }))

    // 自研确认框：点「确定」后才真正删除
    fireEvent.click(await screen.findByRole('button', { name: '确定' }))

    await waitFor(() => expect(mockedChatApi.deleteConversation).toHaveBeenCalledWith(5))
  })

  it('确认框点「取消」时不删除', async () => {
    mockedChatApi.listConversations.mockResolvedValue([
      { id: 5, title: '待删除会话', updated_at: '2026-01-01' },
    ])
    renderPage()

    fireEvent.click(await screen.findByText('待删除会话'))
    fireEvent.click(screen.getByRole('button', { name: '删除会话 待删除会话' }))
    fireEvent.click(await screen.findByRole('button', { name: '取消' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(mockedChatApi.deleteConversation).not.toHaveBeenCalled()
  })

  it('切换会话时中止在途流，旧回答不会串进新会话', async () => {
    const encoder = new TextEncoder()
    const streamRef: { current: ReadableStreamDefaultController<Uint8Array> | null } = {
      current: null,
    }
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        streamRef.current = controller
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(START_EVENT)}\n\n`))
      },
    })
    const fetchMock = vi.fn().mockImplementation((_url, init: RequestInit) => {
      // 模拟 fetch 在 signal 被 abort 时以 AbortError 拒绝
      return new Promise((resolve, reject) => {
        init.signal?.addEventListener('abort', () => {
          reject(Object.assign(new Error('aborted'), { name: 'AbortError' }))
        })
        resolve(new Response(body, { status: 200 }))
      })
    })
    vi.stubGlobal('fetch', fetchMock)

    mockedChatApi.listConversations.mockResolvedValue([
      { id: 3, title: '另一个会话', updated_at: '2026-01-01' },
    ])
    mockedChatApi.getMessages.mockResolvedValue([
      { id: 1, role: 'user', content: '新会话的问题', citations: null, created_at: '' },
    ])

    renderPage()
    await screen.findByText('欢迎使用知识库问答')
    await ask('正在流式回答的问题')

    // 流还没结束就切走
    fireEvent.click(await screen.findByText('另一个会话'))

    expect(await screen.findByText('新会话的问题')).toBeTruthy()
    await waitFor(() => expect(screen.queryByText('正在流式回答的问题')).toBeNull())
    // 请求确实被 abort 了
    const signal = (fetchMock.mock.calls[0][1] as RequestInit).signal
    expect(signal?.aborted).toBe(true)
    streamRef.current?.close()
  })
})