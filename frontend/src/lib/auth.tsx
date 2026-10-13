/**
 * 登录态的唯一数据源。
 *
 * 之前 user 同时存在 localStorage 和 React state 里，两边可能不同步（例如令牌
 * 刷新失败被清掉时，localStorage 空了但 state 还留着人）。现在只保留 React state：
 * 刷新页面时用 /auth/me 重新拉一次，`loading` 期间路由守卫显示加载态，
 * 既不会闪烁、也不会有「看起来已登录其实令牌已失效」的窗口。
 */
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { authApi, clearTokens, getAccessToken, onAuthCleared, setTokens } from './api'
import type { UserInfo } from './types'

interface AuthContextValue {
  user: UserInfo | null
  isAdmin: boolean
  /** 启动时正在校验登录态，此时既不能判定为已登录也不能判定为未登录 */
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null)
  const [loading, setLoading] = useState(true)

  // 令牌被清空（如刷新失败）时同步退出登录态
  useEffect(() => onAuthCleared(() => setUser(null)), [])

  // 启动时校验：有令牌就用 /auth/me 换回用户信息（拦截器会自动刷新过期令牌）
  useEffect(() => {
    if (!getAccessToken()) {
      // 本地压根没有令牌，无需请求后端
      setLoading(false)
      return
    }
    let cancelled = false
    authApi
      .me()
      .then((me) => {
        if (!cancelled) setUser({ id: me.id, username: me.username, is_admin: me.is_admin })
      })
      .catch(() => {
        // 未登录（401）或后端不可用：一律按未登录处理，清掉可能残留的令牌
        clearTokens()
        if (!cancelled) setUser(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const login = async (username: string, password: string) => {
    const tokens = await authApi.login(username, password)
    setTokens(tokens.access_token, tokens.refresh_token)
    const me = await authApi.me()
    setUser({ id: me.id, username: me.username, is_admin: me.is_admin })
  }

  const logout = () => {
    clearTokens()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, isAdmin: !!user?.is_admin, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth 必须在 AuthProvider 内使用')
  return ctx
}