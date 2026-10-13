import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider, useAuth } from './auth'
import { authApi, getAccessToken } from './api'

function Probe() {
  const { user, isAdmin, login, logout } = useAuth()
  return (
    <div>
      <span data-testid="username">{user ? user.username : 'anonymous'}</span>
      <span data-testid="admin">{String(isAdmin)}</span>
      <button onClick={() => login('alice', 'secret')}>登录</button>
      <button onClick={logout}>登出</button>
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
  it('未登录时 user 为空、isAdmin 为 false', () => {
    renderProbe()
    expect(screen.getByTestId('username').textContent).toBe('anonymous')
    expect(screen.getByTestId('admin').textContent).toBe('false')
  })

  it('挂载时从 localStorage 恢复登录态', () => {
    localStorage.setItem('user', JSON.stringify({ id: 1, username: 'boss', is_admin: true }))
    renderProbe()
    expect(screen.getByTestId('username').textContent).toBe('boss')
    expect(screen.getByTestId('admin').textContent).toBe('true')
  })

  it('登录成功后写入令牌、用户信息并更新状态', async () => {
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
    expect(JSON.parse(localStorage.getItem('user')!)).toEqual({
      id: 9,
      username: 'alice',
      is_admin: true,
    })
  })

  it('登出清空令牌与用户信息', async () => {
    localStorage.setItem('user', JSON.stringify({ id: 1, username: 'alice', is_admin: false }))
    localStorage.setItem('access_token', 'access-abc')
    renderProbe()

    fireEvent.click(screen.getByRole('button', { name: '登出' }))

    await waitFor(() => expect(screen.getByTestId('username').textContent).toBe('anonymous'))
    expect(getAccessToken()).toBeNull()
    expect(localStorage.getItem('user')).toBeNull()
  })
})