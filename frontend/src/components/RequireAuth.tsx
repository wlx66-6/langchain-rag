import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'

export default function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  // 校验登录态期间先显示加载态，避免「未登录一闪」或误跳登录页
  if (loading) return <div className="page-loading">加载中…</div>
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}