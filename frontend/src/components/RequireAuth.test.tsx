import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import RequireAuth from './RequireAuth'
import { useAuth } from '../lib/auth'

vi.mock('../lib/auth', () => ({
  useAuth: vi.fn(),
}))

const mockedUseAuth = vi.mocked(useAuth)

function base(overrides: Partial<ReturnType<typeof useAuth>> = {}) {
  return {
    user: null,
    isAdmin: false,
    loading: false,
    login: async () => {},
    logout: () => {},
    ...overrides,
  }
}

function renderGuard() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/login" element={<div>登录页</div>} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <div>受保护内容</div>
            </RequireAuth>
          }
        />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockedUseAuth.mockReset()
})

describe('RequireAuth 鉴权守卫', () => {
  it('未登录时跳转到登录页', () => {
    mockedUseAuth.mockReturnValue(base())
    renderGuard()
    expect(screen.getByText('登录页')).toBeTruthy()
    expect(screen.queryByText('受保护内容')).toBeNull()
  })

  it('已登录时渲染受保护内容', () => {
    mockedUseAuth.mockReturnValue(
      base({ user: { id: 1, username: 'admin', is_admin: true }, isAdmin: true }),
    )
    renderGuard()
    expect(screen.getByText('受保护内容')).toBeTruthy()
  })

  it('校验登录态期间显示加载态，既不跳转也不渲染内容', () => {
    mockedUseAuth.mockReturnValue(base({ loading: true }))
    renderGuard()
    expect(screen.getByText('加载中…')).toBeTruthy()
    expect(screen.queryByText('登录页')).toBeNull()
    expect(screen.queryByText('受保护内容')).toBeNull()
  })
})
