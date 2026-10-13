import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { authApi } from '../lib/api'
import { errorMessage } from '../lib/errors'
import { useUi } from '../lib/ui'

export default function RegisterPage() {
  const navigate = useNavigate()
  const { toast } = useUi()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (loading) return
    setError('')
    if (!username.trim()) {
      setError('请输入用户名')
      return
    }
    if (password.length < 6) {
      setError('密码至少 6 位')
      return
    }
    if (password !== confirm) {
      setError('两次输入的密码不一致')
      return
    }
    setLoading(true)
    try {
      await authApi.register(username.trim(), password)
      toast('注册成功，请登录', 'success')
      navigate('/login')
    } catch (err) {
      setError(errorMessage(err, '注册失败，请重试'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={submit}>
        <h1 className="auth-title">注册账号</h1>
        <div className="auth-sub">注册后即可使用知识库问答</div>

        <div className="form-field">
          <label className="form-label" htmlFor="reg-username">
            用户名
          </label>
          <input
            id="reg-username"
            className="form-input"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoFocus
          />
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="reg-password">
            密码（至少 6 位）
          </label>
          <input
            id="reg-password"
            className="form-input"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="reg-confirm">
            确认密码
          </label>
          <input
            id="reg-confirm"
            className="form-input"
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
        </div>
        <div className="form-error" role="alert">
          {error}
        </div>

        <button className="btn btn-primary btn-block" disabled={loading}>
          {loading ? '注册中…' : '注册'}
        </button>
        <div className="auth-link">
          已有账号？<Link to="/login">去登录</Link>
        </div>
      </form>
    </div>
  )
}