import { createContext, useContext, useState, type ReactNode } from 'react'
import { authApi, clearTokens, setTokens } from './api'

export interface UserInfo {
  id: number
  username: string
  is_admin: boolean
}

interface AuthContextValue {
  user: UserInfo | null
  isAdmin: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(() => {
    const raw = localStorage.getItem('user')
    return raw ? (JSON.parse(raw) as UserInfo) : null
  })

  const login = async (username: string, password: string) => {
    const data = await authApi.login(username, password)
    setTokens(data.access_token, data.refresh_token)
    const me = await authApi.me()
    const u: UserInfo = { id: me.id, username: me.username, is_admin: me.is_admin }
    localStorage.setItem('user', JSON.stringify(u))
    setUser(u)
  }

  const logout = () => {
    clearTokens()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, isAdmin: !!user?.is_admin, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth 必须在 AuthProvider 内使用')
  return ctx
}