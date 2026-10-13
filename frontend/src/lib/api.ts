import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import type { ApiMessage, AuthTokens, Conversation, KnowledgeDocument, UserInfo } from './types'

const ACCESS_KEY = 'access_token'
const REFRESH_KEY = 'refresh_token'
export const USER_KEY = 'user'

export function getAccessToken() {
  return localStorage.getItem(ACCESS_KEY)
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_KEY)
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem(ACCESS_KEY, access)
  localStorage.setItem(REFRESH_KEY, refresh)
}

// ---- 令牌被清空时通知订阅者 ----
// 令牌可能在「刷新失败」时被 api.ts 自己清掉，此时 React 里的登录态也必须同步失效。
// 用订阅回调而不是 window.location 硬跳转，避免整页刷新、也便于测试。
type AuthClearedListener = () => void
const authClearedListeners = new Set<AuthClearedListener>()

export function onAuthCleared(listener: AuthClearedListener): () => void {
  authClearedListeners.add(listener)
  return () => authClearedListeners.delete(listener)
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY)
  localStorage.removeItem(REFRESH_KEY)
  localStorage.removeItem(USER_KEY)
  authClearedListeners.forEach((listener) => listener())
}

// 统一走 vite 代理，前端 /api 请求会被转发到后端 8000 端口
export const api = axios.create({ baseURL: '/api' })

// 每个请求自动带上令牌
api.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 401 时尝试用 refresh_token 换新令牌，成功则重试原请求
let refreshing: Promise<string> | null = null

async function doRefresh(): Promise<string> {
  const refresh = getRefreshToken()
  if (!refresh) throw new Error('no refresh token')
  const res = await axios.post<AuthTokens>('/api/auth/refresh', { refresh_token: refresh })
  setTokens(res.data.access_token, res.data.refresh_token)
  return res.data.access_token
}

/**
 * 用 refresh_token 换新的 access_token。并发调用会复用同一个在途请求，
 * 避免同时刷新导致 refresh_token 被轮换后失效。SSE 请求（见 lib/sse.ts）也复用这里。
 */
export function refreshAccessToken(): Promise<string> {
  refreshing ??= doRefresh().finally(() => {
    refreshing = null
  })
  return refreshing
}

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined
    if (error.response?.status === 401 && original && !original._retry) {
      original._retry = true
      try {
        const token = await refreshAccessToken()
        original.headers.Authorization = `Bearer ${token}`
        return api(original)
      } catch {
        clearTokens() // 会通知 AuthProvider 退出登录，由路由守卫跳回登录页
        return Promise.reject(error)
      }
    }
    return Promise.reject(error)
  },
)

// ============ 各接口封装 ============

export const authApi = {
  login: (username: string, password: string) =>
    api.post<AuthTokens>('/auth/login', { username, password }).then((r) => r.data),
  register: (username: string, password: string) =>
    api.post('/auth/register', { username, password }).then((r) => r.data),
  me: () => api.get<UserInfo>('/auth/me').then((r) => r.data),
  changePassword: (old_password: string, new_password: string) =>
    api.post('/auth/change-password', { old_password, new_password }).then((r) => r.data),
}

export const chatApi = {
  listConversations: (limit = 50, offset = 0) =>
    api.get<Conversation[]>('/conversations', { params: { limit, offset } }).then((r) => r.data),
  createConversation: (title: string) =>
    api.post<Conversation>('/conversations', { title }).then((r) => r.data),
  renameConversation: (id: number, title: string) =>
    api.patch(`/conversations/${id}`, { title }).then((r) => r.data),
  deleteConversation: (id: number) => api.delete(`/conversations/${id}`).then((r) => r.data),
  getMessages: (id: number, limit = 200, offset = 0) =>
    api
      .get<ApiMessage[]>(`/conversations/${id}/messages`, { params: { limit, offset } })
      .then((r) => r.data),
}

export const knowledgeApi = {
  listDocuments: (limit = 100, offset = 0) =>
    api
      .get<KnowledgeDocument[]>('/knowledge/documents', { params: { limit, offset } })
      .then((r) => r.data),
  uploadDocument: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post<KnowledgeDocument>('/knowledge/upload', fd).then((r) => r.data)
  },
  deleteDocument: (id: number) => api.delete(`/knowledge/documents/${id}`).then((r) => r.data),
}
