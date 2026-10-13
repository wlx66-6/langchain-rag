import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { authApi } from '../lib/api'
import { useAuth } from '../lib/auth'
import { errorMessage } from '../lib/errors'
import { useUi } from '../lib/ui'

export default function ProfilePage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const { toast } = useUi()
  const [oldPwd, setOldPwd] = useState('')
  const [newPwd, setNewPwd] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (submitting) return
    setError('')
    if (newPwd.length < 6) {
      setError('新密码至少 6 位')
      return
    }
    if (newPwd !== confirm) {
      setError('两次输入的新密码不一致')
      return
    }
    setSubmitting(true)
    try {
      await authApi.changePassword(oldPwd, newPwd)
      toast('密码修改成功', 'success')
      setOldPwd('')
      setNewPwd('')
      setConfirm('')
    } catch (err) {
      setError(errorMessage(err, '修改失败，请重试'))
    } finally {
      setSubmitting(false)
    }
  }

  const onLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="profile-page">
      <div className="profile-card">
        <h1 className="auth-title">个人中心</h1>
        <div className="auth-sub">
          当前账号：{user?.username}
          {user?.is_admin ? '（管理员）' : ''}
        </div>

        <form onSubmit={submit}>
          <div className="form-field">
            <label className="form-label" htmlFor="old-pwd">
              原密码
            </label>
            <input
              id="old-pwd"
              className="form-input"
              type="password"
              autoComplete="current-password"
              value={oldPwd}
              onChange={(e) => setOldPwd(e.target.value)}
            />
          </div>
          <div className="form-field">
            <label className="form-label" htmlFor="new-pwd">
              新密码（至少 6 位）
            </label>
            <input
              id="new-pwd"
              className="form-input"
              type="password"
              autoComplete="new-password"
              value={newPwd}
              onChange={(e) => setNewPwd(e.target.value)}
            />
          </div>
          <div className="form-field">
            <label className="form-label" htmlFor="confirm-pwd">
              确认新密码
            </label>
            <input
              id="confirm-pwd"
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

          <button className="btn btn-primary btn-block" disabled={submitting}>
            {submitting ? '提交中…' : '修改密码'}
          </button>
        </form>

        <div className="profile-actions">
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
