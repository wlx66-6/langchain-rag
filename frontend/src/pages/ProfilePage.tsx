import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { authApi } from '../lib/api'
import { useAuth } from '../lib/auth'

export default function ProfilePage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [oldPwd, setOldPwd] = useState('')
  const [newPwd, setNewPwd] = useState('')
  const [confirm, setConfirm] = useState('')
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setMsg('')
    setError('')
    if (newPwd.length < 6) {
      setError('新密码至少 6 位')
      return
    }
    if (newPwd !== confirm) {
      setError('两次输入的新密码不一致')
      return
    }
    try {
      await authApi.changePassword(oldPwd, newPwd)
      setMsg('密码修改成功')
      setOldPwd('')
      setNewPwd('')
      setConfirm('')
    } catch (err: any) {
      setError(err?.response?.data?.detail || '修改失败，请重试')
    }
  }

  const onLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="profile-page">
      <div className="profile-card">
        <div className="auth-title">个人中心</div>
        <div className="auth-sub">
          当前账号：{user?.username}
          {user?.is_admin ? '（管理员）' : ''}
        </div>

        <form onSubmit={submit}>
          <div className="form-field">
            <label className="form-label">原密码</label>
            <input
              className="form-input"
              type="password"
              value={oldPwd}
              onChange={(e) => setOldPwd(e.target.value)}
            />
          </div>
          <div className="form-field">
            <label className="form-label">新密码（至少 6 位）</label>
            <input
              className="form-input"
              type="password"
              value={newPwd}
              onChange={(e) => setNewPwd(e.target.value)}
            />
          </div>
          <div className="form-field">
            <label className="form-label">确认新密码</label>
            <input
              className="form-input"
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
          </div>
          <div className="form-error">{error || msg}</div>

          <button className="btn btn-primary btn-block">修改密码</button>
        </form>

        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 16 }}>
          <Link to="/chat" className="btn">
            返回对话
          </Link>
          <button className="btn btn-danger" onClick={onLogout}>
            退出登录
          </button>
        </div>
      </div>
    </div>
  )
}