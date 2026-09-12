import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type KeyboardEvent as RKeyboardEvent,
} from 'react'
import ReactMarkdown from 'react-markdown'
import { Link } from 'react-router-dom'
import remarkGfm from 'remark-gfm'
import { chatApi, getAccessToken } from '../lib/api'
import { useAuth } from '../lib/auth'

interface Source {
  source: string
  content: string
}
interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  sources: Source[]
}
interface Conv {
  id: number
  title: string
  updated_at: string
}

function parseCitations(c?: string | null): Source[] {
  if (!c) return []
  try {
    return JSON.parse(c)
  } catch {
    return []
  }
}

// 单条引用卡片：内容过长时默认收起（只显示前 3 行），点「展开/收起」切换
function CitationCard({ source, content }: Source) {
  const [expanded, setExpanded] = useState(false)
  const long = content.length > 120
  const contentClass = long && !expanded ? 'citation-content collapsed' : 'citation-content'
  return (
    <div className="citation">
      <div
        className={`citation-head${long ? ' clickable' : ''}`}
        onClick={() => long && setExpanded((v) => !v)}
      >
        <span className="citation-source">📄 {source}</span>
        {long && (
          <span className="citation-toggle">{expanded ? '收起 ▲' : '展开 ▼'}</span>
        )}
      </div>
      <div className={contentClass}>{content}</div>
    </div>
  )
}

export default function ChatPage() {
  const { user, isAdmin } = useAuth()
  const [conversations, setConversations] = useState<Conv[]>([])
  const [activeConvId, setActiveConvId] = useState<number | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState('')
  const [sources, setSources] = useState<Source[]>([])
  const [loading, setLoading] = useState(false)

  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const refreshConversations = async () => {
    try {
      setConversations(await chatApi.listConversations())
    } catch {
      /* 忽略 */
    }
  }

  useEffect(() => {
    refreshConversations()
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streaming, sources])

  const selectConversation = async (id: number) => {
    if (loading) return
    setActiveConvId(id)
    setStreaming('')
    setSources([])
    try {
      const raw = await chatApi.getMessages(id)
      setMessages(
        raw.map((m: any) => ({
          id: m.id,
          role: m.role as 'user' | 'assistant',
          content: m.content,
          sources: parseCitations(m.citations),
        })),
      )
    } catch {
      setMessages([])
    }
  }

  const newConversation = () => {
    if (loading) return
    setActiveConvId(null)
    setMessages([])
    setStreaming('')
    setSources([])
    inputRef.current?.focus()
  }

  const deleteConversation = async (id: number) => {
    if (!window.confirm('确定删除该会话吗？')) return
    await chatApi.deleteConversation(id)
    if (activeConvId === id) newConversation()
    refreshConversations()
  }

  const handleInput = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 160) + 'px'
  }

  const send = async () => {
    const text = input.trim()
    if (!text || loading || streaming !== '') return
    setInput('')
    setMessages((prev) => [
      ...prev,
      { id: Date.now(), role: 'user', content: text, sources: [] },
    ])
    setStreaming('')
    setSources([])
    setLoading(true)

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${getAccessToken()}`,
        },
        body: JSON.stringify({ conversation_id: activeConvId, content: text }),
      })

      if (res.status === 401) {
        window.location.href = '/login'
        return
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || '请求失败，请重试')
      }

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      let assistantText = ''
      let finalSources: Source[] = []

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const events = buf.split('\n\n')
        buf = events.pop() ?? ''
        for (const ev of events) {
          const line = ev.split('\n').find((l) => l.startsWith('data:'))
          if (!line) continue
          const payload = JSON.parse(line.slice(5).trim())
          if (payload.type === 'start') {
            const { conversation_id, sources: srcs } = payload.data
            if (conversation_id != null && conversation_id !== activeConvId) {
              setActiveConvId(conversation_id)
              refreshConversations()
            }
            finalSources = srcs
            setSources(srcs)
          } else if (payload.type === 'token') {
            assistantText += payload.data
            setStreaming(assistantText)
          } else if (payload.type === 'error') {
            throw new Error(payload.data)
          }
        }
      }

      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          role: 'assistant',
          content: assistantText || '（未能生成回答）',
          sources: finalSources,
        },
      ])
      setStreaming('')
    } catch (err: any) {
      window.alert(err?.message || '发送失败，请重试')
      setStreaming('')
    } finally {
      setLoading(false)
    }
  }

  const onKeyDown = (e: RKeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

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
            <div style={{ padding: 12, color: 'var(--text-muted)', fontSize: 14 }}>
              暂无会话，点击「新建」开始
            </div>
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
              {m.role === 'assistant' && m.sources.length > 0 && (
                <div className="citations">
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>
                    引用资料
                  </div>
                  {m.sources.map((s, i) => (
                    <CitationCard key={i} source={s.source} content={s.content} />
                  ))}
                </div>
              )}
            </div>
          ))}

          {streaming !== '' && (
            <div className="msg assistant">
              <div className="bubble streaming-cursor">
                <div className="md">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{streaming}</ReactMarkdown>
                </div>
              </div>
              {sources.length > 0 && (
                <div className="citations">
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>
                    引用资料
                  </div>
                  {sources.map((s, i) => (
                    <CitationCard key={i} source={s.source} content={s.content} />
                  ))}
                </div>
              )}
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        <div className="input-bar">
          <textarea
            ref={inputRef}
            className="input-textarea"
            placeholder="请输入问题，Enter 发送，Shift+Enter 换行"
            value={input}
            onChange={handleInput}
            onKeyDown={onKeyDown}
            rows={1}
          />
          <button
            className="btn btn-primary send-btn"
            onClick={send}
            disabled={loading || !input.trim()}
          >
            {loading ? '思考中…' : '发送'}
          </button>
        </div>
      </main>
    </div>
  )
}