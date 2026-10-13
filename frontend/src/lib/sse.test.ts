import { afterEach, describe, expect, it, vi } from 'vitest'
import { getAccessToken, refreshAccessToken } from './api'
import { StreamError, streamChat } from './sse'

vi.mock('./api', () => ({
  getAccessToken: vi.fn(),
  refreshAccessToken: vi.fn(),
}))

const mockedGetAccessToken = vi.mocked(getAccessToken)
const mockedRefresh = vi.mocked(refreshAccessToken)

function sseResponse(events: object[], status = 200): Response {
  const encoder = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const e of events) controller.enqueue(encoder.encode(`data: ${JSON.stringify(e)}\n\n`))
      controller.close()
    },
  })
  return new Response(body, { status })
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('streamChat', () => {
  it('解析 start / token 事件并返回累计文本与引用', async () => {
    mockedGetAccessToken.mockReturnValue('token-abc')
    const onStart = vi.fn()
    const onToken = vi.fn()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        sseResponse([
          {
            type: 'start',
            data: { conversation_id: 5, sources: [{ source: 'a.txt', content: '内容' }] },
          },
          { type: 'token', data: '你好' },
          { type: 'token', data: '，世界' },
          { type: 'done' },
        ]),
      ),
    )

    const result = await streamChat({
      conversationId: null,
      content: '问题',
      onStart,
      onToken,
    })

    expect(result.text).toBe('你好，世界')
    expect(result.conversationId).toBe(5)
    expect(result.citations).toEqual([{ source: 'a.txt', content: '内容' }])
    expect(onStart).toHaveBeenCalledWith(5, [{ source: 'a.txt', content: '内容' }])
    expect(onToken).toHaveBeenLastCalledWith('你好，世界')
  })

  it('事件被切断成半截 JSON 时忽略该段，不影响已收到的内容', async () => {
    mockedGetAccessToken.mockReturnValue('token-abc')
    const encoder = new TextEncoder()
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('data: {"type":"token","data":"好"}\n\n'))
        controller.enqueue(encoder.encode('data: {"type":"tok'))
        controller.close()
      },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, { status: 200 })))

    const result = await streamChat({ conversationId: null, content: '问题' })
    expect(result.text).toBe('好')
  })

  it('401 时刷新令牌并重试一次', async () => {
    mockedGetAccessToken.mockReturnValue('old-token')
    mockedRefresh.mockResolvedValue('new-token')
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response('', { status: 401 }))
      .mockResolvedValueOnce(sseResponse([{ type: 'token', data: '成功' }]))
    vi.stubGlobal('fetch', fetchMock)

    const result = await streamChat({ conversationId: null, content: '问题' })

    expect(result.text).toBe('成功')
    expect(mockedRefresh).toHaveBeenCalledTimes(1)
    expect((fetchMock.mock.calls[1][1] as RequestInit).headers).toMatchObject({
      Authorization: 'Bearer new-token',
    })
  })

  it('刷新失败时抛 unauthorized 错误', async () => {
    mockedGetAccessToken.mockReturnValue('old-token')
    mockedRefresh.mockRejectedValue(new Error('refresh failed'))
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 401 })))

    await expect(streamChat({ conversationId: null, content: '问题' })).rejects.toMatchObject({
      code: 'unauthorized',
    })
  })

  it('非 2xx 且非 401 时抛出后端 detail', async () => {
    mockedGetAccessToken.mockReturnValue('token-abc')
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(new Response(JSON.stringify({ detail: '会话不存在' }), { status: 404 })),
    )

    await expect(streamChat({ conversationId: 1, content: '问题' })).rejects.toThrow('会话不存在')
  })

  it('收到 error 事件时抛出 StreamError 并带上 code', async () => {
    mockedGetAccessToken.mockReturnValue('token-abc')
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          sseResponse([{ type: 'error', data: '生成失败', code: 'generation_failed' }]),
        ),
    )

    const err = await streamChat({ conversationId: null, content: '问题' }).catch((e) => e)
    expect(err).toBeInstanceOf(StreamError)
    expect(err.code).toBe('generation_failed')
    expect(err.message).toBe('生成失败')
  })

  it('signal 被取消时以 AbortError 拒绝', async () => {
    mockedGetAccessToken.mockReturnValue('token-abc')
    const controller = new AbortController()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((_url: string, init: RequestInit) => {
        return new Promise((_resolve, reject) => {
          init.signal?.addEventListener('abort', () =>
            reject(Object.assign(new Error('aborted'), { name: 'AbortError' })),
          )
        })
      }),
    )

    const promise = streamChat({ conversationId: null, content: '问题', signal: controller.signal })
    controller.abort()

    await expect(promise).rejects.toMatchObject({ name: 'AbortError' })
  })
})
