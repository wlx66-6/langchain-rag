import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type KeyboardEvent as RKeyboardEvent,
} from 'react'
import ReactMarkdown from 'react-markdown'
import { Link } from 'react-router-dom'
import remarkGfm from 'remark-gfm'
import { chatApi } from '../lib/api'
import { useAuth } from '../lib/auth'
import { errorMessage } from '../lib/errors'
import { streamChat } from '../lib/sse'
import type { ApiMessage, ChatMessage, Citation, Conversation } from '../lib/types'
import { useUi } from '../lib/ui'

/** 后端把引用存成 JSON 字符串，解析失败（脏数据）时当作没有引用。 */
function parseCitations(raw?: string | null): Citation[] {
  if (!raw) return []
  try {
    const parsed: unknown = JSON.parse(raw)
    return Array.isArray(parsed) ? (parsed as Citation[]) : []
  } catch {
    return []
  }
}

// 单条引用卡片：内容过长时默认收起（只显示前 3 行），点「展开/收起」切换
function CitationCard({ source, content }: Citation) {
  const [expanded, setExpanded] = useState(false)
  const long = content.length > 120
  const contentClass = long && !expanded ? 'citation-content collapsed' : 'citation-content'
  return (
    <div className="citation">
      <button
        type="button"
        className={`citation-head${long ? ' clickable' : ''}`}
        onClick={() => long && setExpanded((v) => !v)}
        aria-expanded={long ? expanded : undefined}
      >
        <span className="citation-source">📄 {source}</span>
        {long && <span className="citation-toggle">{expanded ? '收起 ▲' : '展开 ▼'}</span>}
      </button>
      <div className={contentClass}>{content}</div>
    </div>
  )
}

export default function ChatPage() {
  const { user, isAdmin } = useAuth()
  const { toast, confirm } = useUi()

  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConvId, setActiveConvId] = useState<number | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState('')
  const [sources, setSources] = useState<Citation[]>([])
  const [sending, setSending] = useState(false)

  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  // 在途请求的取消器与序号：切会话/卸载时中止旧流，序号用来丢弃过期回调
  const abortRef = useRef<AbortController | null>(null)
  const streamSeq = useRef(0)

  const cancelStream = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setSending(false) // 主动取消时发送态由这里复位（send 的 finally 会因序号变化而跳过）
  }, [])

  // 组件卸载时中止在途流，避免回调继续 setState
  useEffect(() => cancelStream, [cancelStream])

  const refreshConversations = useCallback(async () => {
    try {
      setConversations(await chatApi.listConversations())
    } catch (err) {
      toast(errorMessage(err, '会话列表加载失败'), 'error')
    }
  }, [toast])

  useEffect(() => {
    refreshConversations()
  }, [refreshConversations])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streaming, sources])

  const selectConversation = async (id: number) => {
    // 允许流式回答期间切走：取消在途请求，避免旧流的回调污染新会话的消息
    cancelStream()
    streamSeq.current += 1 // 让旧流已发出的回调失效
    setActiveConvId(id)
    setStreaming('')
    setSources([])
    try {
      const raw = await chatApi.getMessages(id)
      setMessages(
        raw.map((m: ApiMessage) => ({
          id: m.id,
          role: m.role === 'assistant' ? 'assistant' : 'user',
          content: m.content,
          citations: parseCitations(m.citations),
        })),
      )
    } catch (err) {
      setMessages([])
      toast(errorMessage(err, '历史消息加载失败'), 'error')
    }
  }

  const newConversation = () => {
    cancelStream()
    streamSeq.current += 1
    setActiveConvId(null)
    setMessages([])
    setStreaming('')
    setSources([])
    inputRef.current?.focus()
  }

  const deleteConversation = async (id: number) => {
    if (!(await confirm('确定删除该会话吗？删除后无法恢复。'))) return
    try {
      await chatApi.deleteConversation(id)
      if (activeConvId === id) newConversation()
      await refreshConversations()
      toast('会话已删除', 'success')
    } catch (err) {
      toast(errorMessage(err, '删除失败，请重试'), 'error')
    }
  }

  const handleInput = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }

  const send = async () => {
    const text = input.trim()
    if (!text || sending) return
    setInput('')
    setMessages((prev) => [...prev, { id: Date.now(), role: 'user', content: text, citations: [] }])
    setStreaming('')
    setSources([])
    setSending(true)

    const seq = ++streamSeq.current
    const controller = new AbortController()
    abortRef.current = controller

    try {
      const result = await streamChat({
        conversationId: activeConvId,
        content: text,
        signal: controller.signal,
        onStart: (convId, citations) => {
          if (streamSeq.current !== seq) return
          if (convId != null && convId !== activeConvId) {
            setActiveConvId(convId) // 后端新建了会话，记下它的 ID
            refreshConversations()
          }
          setSources(citations)
        },
        onToken: (accumulated) => {
          if (streamSeq.current === seq) setStreaming(accumulated)
        },
      })

      if (streamSeq.current !== seq) return // 已被切会话/新建打断，丢弃结果
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          role: 'assistant',
          content: result.text || '（未能生成回答）',
          citations: result.citations,
        },
      ])
      setStreaming('')
    } catch (err) {
      if (controller.signal.aborted) return // 主动取消，静默处理
      if (streamSeq.current !== seq) return
      toast(errorMessage(err, '发送失败，请重试'), 'error')
      setStreaming('')
    } finally {
      if (abortRef.current === controller) abortRef.current = null
      if (streamSeq.current === seq) setSending(false)
    }
  }

  const onKeyDown = (e: RKeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  const renderCitations = (items: Citation[]) => (
    <div className="citations">
      <div className="citations-title">引用资料</div>
      {items.map((s, i) => (
        <CitationCard key={i} source={s.source} content={s.content} />
      ))}
    </div>
  )

  return (
    <div className="chat-layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <span className="sidebar-title">会话列表</span>
          <button className="btn btn-primary new-conv-btn" onClick={newConversation}>
            ＋ 新建
          </button>
        </div>
        <div className="conv-list">
          {conversations.length === 0 && (
            <div className="conv-empty">暂无会话，点击「新建」开始</div>
          )}
          {conversations.map((c) => (
            <div
              key={c.id}
              className={`conv-item ${c.id === activeConvId ? 'active' : ''}`}
              onClick={() => selectConversation(c.id)}
            >
              <span className="conv-title">{c.title}</span>
              <button
                className="conv-del"
                aria-label={`删除会话 ${c.title}`}
                onClick={(e) => {
                  e.stopPropagation()
                  deleteConversation(c.id)
                }}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
        <div className="sidebar-footer">
          <div className="user-chip">
            {user?.username}
            {isAdmin && <span className="admin-tag">管理员</span>}
          </div>
          <div className="nav-links">
            {isAdmin && <Link to="/knowledge">知识库</Link>}
            <Link to="/profile">个人中心</Link>
          </div>
        </div>
      </aside>

      <main className="chat-main">
        <div className="chat-header">
          {activeConvId ? '当前会话' : '新会话 · 向我提问商品相关问题'}
        </div>

        <div className="messages">
          {messages.length === 0 && streaming === '' && (
            <div className="empty-state">
              <h2>欢迎使用知识库问答</h2>
              <p>输入商品相关问题，我会基于知识库为你解答并标注引用出处</p>
            </div>
          )}

          {messages.map((m) => (
            <div key={m.id} className={`msg ${m.role}`}>
              <div className="bubble">
                {m.role === 'assistant' ? (
                  <div className="md">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                  </div>
                ) : (
                  m.content
                )}
              </div>
              {m.role === 'assistant' && m.citations.length > 0 && renderCitations(m.citations)}
            </div>
          ))}

          {streaming !== '' && (
            <div className="msg assistant">
              <div className="bubble streaming-cursor">
                <div className="md">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{streaming}</ReactMarkdown>
                </div>
              </div>
              {sources.length > 0 && renderCitations(sources)}
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        <div className="input-bar">
          <textarea
            ref={inputRef}
            className="input-textarea"
            aria-label="输入问题"
            placeholder="请输入问题，Enter 发送，Shift+Enter 换行"
            value={input}
            onChange={handleInput}
            onKeyDown={onKeyDown}
            rows={1}
          />
          <button
            className="btn btn-primary send-btn"
            onClick={send}
            disabled={sending || !input.trim()}
          >
            {sending ? '思考中…' : '发送'}
          </button>
        </div>
      </main>
    </div>
  )
}
