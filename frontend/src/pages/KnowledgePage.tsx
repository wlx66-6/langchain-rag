import { useEffect, useRef, useState, type ChangeEvent } from 'react'
import { Link } from 'react-router-dom'
import { knowledgeApi } from '../lib/api'
import { useAuth } from '../lib/auth'

interface Doc {
  id: number
  filename: string
  file_type: string
  status: string
  chunk_count: number
  created_at: string
}

export default function KnowledgePage() {
  const { isAdmin } = useAuth()
  const [docs, setDocs] = useState<Doc[]>([])
  const [uploading, setUploading] = useState(false)
  const [msg, setMsg] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const refresh = async () => {
    try {
      setDocs(await knowledgeApi.listDocuments())
    } catch (err: any) {
      setMsg(err?.response?.data?.detail || '加载失败')
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  const onUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setMsg('')
    setUploading(true)
    try {
      await knowledgeApi.uploadDocument(file)
      setMsg(`「${file.name}」上传成功，已入库`)
      refresh()
    } catch (err: any) {
      setMsg(err?.response?.data?.detail || '上传失败')
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const onDelete = async (d: Doc) => {
    if (!window.confirm(`确定删除「${d.filename}」吗？将同时从知识库中移除对应内容`)) return
    await knowledgeApi.deleteDocument(d.id)
    refresh()
  }

  if (!isAdmin) {
    return (
      <div className="kb-page">
        <div className="empty-state">
          <h2>无权限访问</h2>
          <p>只有管理员才能打开知识库管理页面</p>
          <Link to="/chat" className="btn btn-primary">
            返回对话
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="kb-page">
      <div className="kb-header">
        <div className="kb-title">知识库管理</div>
        <Link to="/chat" className="btn">
          返回对话
        </Link>
      </div>

      <div className="upload-zone">
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.docx,.xlsx,.xlsm,.txt,.md,.markdown,.csv"
          onChange={onUpload}
          disabled={uploading}
        />
        <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>
          支持 PDF / Word / Excel / TXT / Markdown / CSV
          {uploading ? '　正在上传解析，请稍候…' : ''}
        </span>
      </div>

      {msg && (
        <div className="form-error" style={{ marginBottom: 12 }}>
          {msg}
        </div>
      )}

      <table className="kb-table">
        <thead>
          <tr>
            <th>文件名</th>
            <th>类型</th>
            <th>片段数</th>
            <th>状态</th>
            <th>上传时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {docs.length === 0 && (
            <tr>
              <td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
                暂无文档，请先上传
              </td>
            </tr>
          )}
          {docs.map((d) => (
            <tr key={d.id}>
              <td>{d.filename}</td>
              <td>{d.file_type}</td>
              <td>{d.chunk_count}</td>
              <td>
                <span className={`status-badge ${d.status}`}>
                  {d.status === 'ready' ? '已入库' : '失败'}
                </span>
              </td>
              <td>{new Date(d.created_at).toLocaleString()}</td>
              <td>
                <button className="btn btn-danger" onClick={() => onDelete(d)}>
                  删除
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}