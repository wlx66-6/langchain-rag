import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'

const ACCESS_KEY = 'access_token'
const REFRESH_KEY = 'refresh_token'

export function getAccessToken() {
  return localStorage.getItem(ACCESS_KEY)
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem(ACCESS_KEY, access)
  localStorage.setItem(REFRESH_KEY, refresh)
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY)
  localStorage.removeItem(REFRESH_KEY)
  localStorage.removeItem('user')
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
  const refresh = localStorage.getItem(REFRESH_KEY)
  if (!refresh) throw new Error('no refresh token')
  const res = await axios.post('/api/auth/refresh', { refresh_token: refresh })
  setTokens(res.data.access_token, res.data.refresh_token)
  return res.data.access_token
}

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined
    if (error.response?.status === 401 && original && !original._retry) {
      original._retry = true
      try {
        refreshing = refreshing ?? doRefresh().finally(() => (refreshing = null))
        const token = await refreshing
        original.headers.Authorization = `Bearer ${token}`
        return api(original)
      } catch {
        clearTokens()
        window.location.href = '/login'
        return Promise.reject(error)
      }
    }
    return Promise.reject(error)
  },
)

// ============ 各接口封装 ============

export const authApi = {
  login: (username: string, password: string) =>
    api.post('/auth/login', { username, password }).then((r) => r.data),
  register: (username: string, password: string) =>
    api.post('/auth/register', { username, password }).then((r) => r.data),
  me: () => api.get('/auth/me').then((r) => r.data),
  changePassword: (old_password: string, new_password: string) =>
    api.post('/auth/change-password', { old_password, new_password }).then((r) => r.data),
}

export const chatApi = {
  listConversations: () => api.get('/conversations').then((r) => r.data),
  createConversation: (title: string) =>
    api.post('/conversations', { title }).then((r) => r.data),
  renameConversation: (id: number, title: string) =>
    api.patch(`/conversations/${id}`, { title }).then((r) => r.data),
  deleteConversation: (id: number) => api.delete(`/conversations/${id}`).then((r) => r.data),
  getMessages: (id: number) => api.get(`/conversations/${id}/messages`).then((r) => r.data),
}

export const knowledgeApi = {
  listDocuments: () => api.get('/knowledge/documents').then((r) => r.data),
  uploadDocument: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post('/knowledge/upload', fd).then((r) => r.data)
  },
  deleteDocument: (id: number) => api.delete(`/knowledge/documents/${id}`).then((r) => r.data),
}