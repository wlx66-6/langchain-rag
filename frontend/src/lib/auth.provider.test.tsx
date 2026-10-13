import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider, useAuth } from './auth'
import { authApi, clearTokens, getAccessToken, setTokens } from './api'

function Probe() {
  const { user, isAdmin, loading, login, logout } = useAuth()
  return (
    <div>
      <span data-testid="username">{user ? user.username : 'anonymous'}</span>
      <span data-testid="admin">{String(isAdmin)}</span>
      <span data-testid="loading">{String(loading)}</span>
      <button onClick={() => login('alice', 'secret')}>登录</button>
      <button onClick={logout}>登出</button>
      <button onClick={clearTokens}>令牌失效</button>
    </div>
  )
}

function renderProbe() {
  return render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  )
}

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('AuthProvider', () => {
  it('本地没有令牌时直接结束校验，user 为空', async () => {
    renderProbe()
    expect(screen.getByTestId('username').textContent).toBe('anonymous')
    expect(screen.getByTestId('admin').textContent).toBe('false')
    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('false'))
  })

  it('有令牌时用 /auth/me 校验并恢复登录态', async () => {
    setTokens('access-abc', 'refresh-xyz')
    vi.spyOn(authApi, 'me').mockResolvedValue({ id: 7, username: 'boss', is_admin: true })

    renderProbe()

    await waitFor(() => expect(screen.getByTestId('username').textContent).toBe('boss'))
    expect(screen.getByTestId('admin').textContent).toBe('true')
    expect(screen.getByTestId('loading').textContent).toBe('false')
  })

  it('/auth/me 失败时清空令牌并判定为未登录', async () => {
    setTokens('access-abc', 'refresh-xyz')
    vi.spyOn(authApi, 'me').mockRejectedValue(new Error('401'))

    renderProbe()

    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('false'))
    expect(screen.getByTestId('username').textContent).toBe('anonymous')
    expect(getAccessToken()).toBeNull()
  })

  it('登录成功后写入令牌并更新状态', async () => {
    vi.spyOn(authApi, 'login').mockResolvedValue({
      access_token: 'access-abc',
      refresh_token: 'refresh-xyz',
    })
    vi.spyOn(authApi, 'me').mockResolvedValue({ id: 9, username: 'alice', is_admin: true })

    renderProbe()
    fireEvent.click(screen.getByRole('button', { name: '登录' }))

    await waitFor(() => expect(screen.getByTestId('username').textContent).toBe('alice'))
    expect(screen.getByTestId('admin').textContent).toBe('true')
    expect(getAccessToken()).toBe('access-abc')
  })

  it('令牌被外部清空时同步退出登录态', async () => {
    vi.spyOn(authApi, 'me').mockResolvedValue({ id: 9, username: 'alice', is_admin: false })
    setTokens('access-abc', 'refresh-xyz')
    renderProbe()
    await waitFor(() => expect(screen.getByTestId('username').textContent).toBe('alice'))

    fireEvent.click(screen.getByRole('button', { name: '令牌失效' }))

    await waitFor(() => expect(screen.getByTestId('username').textContent).toBe('anonymous'))
  })

  it('登出清空令牌与登录态', async () => {
    vi.spyOn(authApi, 'me').mockResolvedValue({ id: 9, username: 'alice', is_admin: false })
    setTokens('access-abc', 'refresh-xyz')
    renderProbe()
    await waitFor(() => expect(screen.getByTestId('username').textContent).toBe('alice'))

    fireEvent.click(screen.getByRole('button', { name: '登出' }))

    await waitFor(() => expect(screen.getByTestId('username').textContent).toBe('anonymous'))
    expect(getAccessToken()).toBeNull()
  })
})
