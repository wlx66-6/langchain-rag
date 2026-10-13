/**
 * SSE 流式问答客户端。
 *
 * 单独抽成模块的原因：这段逻辑（带令牌 → 401 刷新重试 → 逐块解析 data: 事件）
 * 既不属于 axios 的封装，也不属于某个页面。放在组件里会导致：
 * 1. 切会话 / 卸载组件后旧流仍在跑，回调继续 setState（React 会警告、UI 会串数据）；
 * 2. 令牌过期时直接跳登录，绕过了 api.ts 的刷新机制。
 * 这里用 AbortSignal 支持取消，并复用 refreshAccessToken()，两处都解决。
 */
import { getAccessToken, refreshAccessToken } from './api'
import type { Citation } from './types'

export class StreamError extends Error {
  code: string

  constructor(message: string, code = 'stream_error') {
    super(message)
    this.name = 'StreamError'
    this.code = code
  }
}

export interface StreamResult {
  text: string
  citations: Citation[]
  conversationId: number | null
}

export interface StreamHandlers {
  /** 收到 start 事件：拿到会话 ID 与引用列表 */
  onStart?: (conversationId: number | null, citations: Citation[]) => void
  /** 每收到一段增量文本回调一次（累计后的完整文本） */
  onToken?: (accumulated: string) => void
}

interface StreamChatParams extends StreamHandlers {
  conversationId: number | null
  content: string
  signal?: AbortSignal
}

interface StartPayload {
  conversation_id?: number
  sources?: Citation[]
}

interface SseEvent {
  type: string
  data?: unknown
  code?: string
}

function parseEvent(raw: string): SseEvent | null {
  try {
    const parsed: unknown = JSON.parse(raw)
    if (parsed && typeof parsed === 'object' && 'type' in parsed) return parsed as SseEvent
  } catch {
    /* 半截 JSON（流被切断）直接忽略，不影响已收到的内容 */
  }
  return null
}

function doFetch(token: string | null, body: string, signal?: AbortSignal): Promise<Response> {
  return fetch('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body,
    signal,
  })
}

/** 读取响应体，逐块解析 SSE 事件并回调。返回累计文本、引用与会话 ID。 */
async function consume(
  res: Response,
  initialConversationId: number | null,
  handlers: StreamHandlers,
): Promise<StreamResult> {
  if (!res.body) throw new StreamError('服务端未返回数据流', 'no_body')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let text = ''
  let citations: Citation[] = []
  let conversationId = initialConversationId

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    // SSE 以空行分隔事件；最后一段可能不完整，留在 buffer 里等下一块
    const chunks = buffer.split('\n\n')
    buffer = chunks.pop() ?? ''
    for (const chunk of chunks) {
      const line = chunk.split('\n').find((l) => l.startsWith('data:'))
      if (!line) continue
      const event = parseEvent(line.slice(5).trim())
      if (!event) continue

      if (event.type === 'start') {
        const payload = (event.data ?? {}) as StartPayload
        if (typeof payload.conversation_id === 'number') conversationId = payload.conversation_id
        citations = Array.isArray(payload.sources) ? payload.sources : []
        handlers.onStart?.(conversationId, citations)
      } else if (event.type === 'token') {
        text += String(event.data ?? '')
        handlers.onToken?.(text)
      } else if (event.type === 'error') {
        throw new StreamError(String(event.data ?? '生成回答失败'), event.code ?? 'generation_failed')
      }
    }
  }

  return { text, citations, conversationId }
}

/**
 * 发起一次流式问答。
 *
 * @throws {StreamError} 请求失败、服务端返回 error 事件或流异常时抛出。
 * @throws {DOMException} 当 `signal` 被取消（AbortError）时由 fetch 抛出，调用方
 *   可用 `signal.aborted` 判断是主动取消而非真失败。
 */
export async function streamChat(params: StreamChatParams): Promise<StreamResult> {
  const { conversationId, content, signal, ...handlers } = params
  const body = JSON.stringify({ conversation_id: conversationId, content })

  let res = await doFetch(getAccessToken(), body, signal)

  if (res.status === 401) {
    // 令牌过期：走与 api.ts 相同的刷新流程，成功后重试一次
    let freshToken: string
    try {
      freshToken = await refreshAccessToken()
    } catch {
      throw new StreamError('登录状态已过期，请重新登录', 'unauthorized')
    }
    res = await doFetch(freshToken, body, signal)
  }

  if (!res.ok) {
    const err = (await res.json().catch(() => null)) as { detail?: string } | null
    throw new StreamError(err?.detail ?? '请求失败，请重试', 'http_error')
  }

  return consume(res, conversationId, handlers)
}