import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import App from './App'
import { useAuth } from './lib/auth'

vi.mock('./lib/auth', () => ({ useAuth: vi.fn() }))
vi.mock('./lib/api', () => ({
  chatApi: { listConversations: vi.fn().mockResolvedValue([]) },
  authApi: { login: vi.fn(), register: vi.fn(), me: vi.fn(), changePassword: vi.fn() },
  knowledgeApi: {
    listDocuments: vi.fn().mockResolvedValue([]),
    uploadDocument: vi.fn(),
    deleteDocument: vi.fn(),
  },
  getAccessToken: vi.fn().mockReturnValue(null),
  setTokens: vi.fn(),
  clearTokens: vi.fn(),
}))

const mockedUseAuth = vi.mocked(useAuth)

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockedUseAuth.mockReturnValue({
    user: null,
    isAdmin: false,
    login: vi.fn(),
    logout: vi.fn(),
  })
})

describe('App 路由', () => {
  it('/login 渲染登录页', () => {
    renderAt('/login')
    expect(screen.getByText('电商知识库问答系统')).toBeTruthy()
  })

  it('/register 渲染注册页', () => {
    renderAt('/register')
    expect(screen.getByText('注册账号')).toBeTruthy()
  })

  it('未登录访问受保护路由时重定向到登录页', () => {
    renderAt('/chat')
    expect(screen.getByText('电商知识库问答系统')).toBeTruthy()
  })

  it('未知路径重定向到登录页（未登录）', () => {
    renderAt('/no-such-page')
    expect(screen.getByText('电商知识库问答系统')).toBeTruthy()
  })

  it('已登录时可以进入受保护路由', () => {
    mockedUseAuth.mockReturnValue({
      user: { id: 1, username: 'alice', is_admin: false },
      isAdmin: false,
      login: vi.fn(),
      logout: vi.fn(),
    })
    renderAt('/chat')
    expect(screen.getByText('欢迎使用知识库问答')).toBeTruthy()
  })
})