import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(username.trim(), password)
      navigate('/chat')
    } catch (err: any) {
      setError(err?.response?.data?.detail || '登录失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={submit}>
        <div className="auth-title">电商知识库问答系统</div>
        <div className="auth-sub">登录后即可开始智能商品问答</div>

        <div className="form-field">
          <label className="form-label">用户名</label>
          <input
            className="form-input"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoFocus
          />
        </div>
        <div className="form-field">
          <label className="form-label">密码</label>
          <input
            className="form-input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <div className="form-error">{error}</div>

        <button className="btn btn-primary btn-block" disabled={loading}>
          {loading ? '登录中…' : '登录'}
        </button>
        <div className="auth-link">
          还没有账号？<Link to="/register">去注册</Link>
        </div>
      </form>
    </div>
  )
}