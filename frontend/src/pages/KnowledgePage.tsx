import { useCallback, useEffect, useRef, useState, type ChangeEvent } from 'react'
import { Link } from 'react-router-dom'
import { knowledgeApi } from '../lib/api'
import { useAuth } from '../lib/auth'
import { errorMessage } from '../lib/errors'
import type { KnowledgeDocument } from '../lib/types'
import { useUi } from '../lib/ui'

const ACCEPT = '.pdf,.docx,.xlsx,.xlsm,.txt,.md,.markdown,.csv'

export default function KnowledgePage() {
  const { isAdmin } = useAuth()
  const { toast, confirm } = useUi()
  const [docs, setDocs] = useState<KnowledgeDocument[]>([])
  const [uploading, setUploading] = useState(false)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const refresh = useCallback(async () => {
    try {
      setDocs(await knowledgeApi.listDocuments())
    } catch (err) {
      toast(errorMessage(err, '文档列表加载失败'), 'error')
    }
  }, [toast])

  useEffect(() => {
    // 非管理员没有权限，连请求都不用发（后端也会返回 403）
    if (isAdmin) refresh()
  }, [isAdmin, refresh])

  const onUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      await knowledgeApi.uploadDocument(file)
      toast(`「${file.name}」上传成功，已入库`, 'success')
      await refresh()
    } catch (err) {
      toast(errorMessage(err, '上传失败，请重试'), 'error')
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const onDelete = async (doc: KnowledgeDocument) => {
    const ok = await confirm(`确定删除「${doc.filename}」吗？将同时从知识库中移除对应内容。`)
    if (!ok) return
    setDeletingId(doc.id)
    try {
      await knowledgeApi.deleteDocument(doc.id)
      toast('文档已删除', 'success')
      await refresh()
    } catch (err) {
      toast(errorMessage(err, '删除失败，请重试'), 'error')
    } finally {
      setDeletingId(null)
    }
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
          accept={ACCEPT}
          onChange={onUpload}
          disabled={uploading}
          aria-label="选择要上传的文档"
        />
        <span className="upload-hint">
          支持 PDF / Word / Excel / TXT / Markdown / CSV
          {uploading ? '　正在上传解析，请稍候…' : ''}
        </span>
      </div>

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
              <td colSpan={6} className="kb-empty">
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
                <button
                  className="btn btn-danger"
                  onClick={() => onDelete(d)}
                  disabled={deletingId === d.id}
                >
                  {deletingId === d.id ? '删除中…' : '删除'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}