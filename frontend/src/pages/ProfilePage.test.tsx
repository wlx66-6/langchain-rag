import { fireEvent, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Route, Routes } from 'react-router-dom'
import ProfilePage from './ProfilePage'
import { authApi } from '../lib/api'
import { useAuth } from '../lib/auth'
import { apiError } from '../test/fixtures'
import { renderWithProviders } from '../test/render'

vi.mock('../lib/api', () => ({ authApi: { changePassword: vi.fn() } }))
vi.mock('../lib/auth', () => ({ useAuth: vi.fn() }))

const changePasswordMock = vi.mocked(authApi.changePassword)
const mockedUseAuth = vi.mocked(useAuth)
const logoutMock = vi.fn()

function renderPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/profile" element={<ProfilePage />} />
      <Route path="/login" element={<div>登录页</div>} />
      <Route path="/chat" element={<div>聊天页</div>} />
    </Routes>,
    '/profile',
  )
}

function fill(container: HTMLElement, oldPwd: string, newPwd: string, confirm: string) {
  const pwds = container.querySelectorAll('input[type="password"]')
  fireEvent.change(pwds[0], { target: { value: oldPwd } })
  fireEvent.change(pwds[1], { target: { value: newPwd } })
  fireEvent.change(pwds[2], { target: { value: confirm } })
}

beforeEach(() => {
  changePasswordMock.mockReset()
  logoutMock.mockReset()
  mockedUseAuth.mockReturnValue({
    user: { id: 1, username: 'alice', is_admin: false },
    isAdmin: false,
    loading: false,
    login: vi.fn(),
    logout: logoutMock,
  })
})

describe('ProfilePage', () => {
  it('展示当前用户名', () => {
    renderPage()
    expect(screen.getByText(/当前账号：alice/)).toBeTruthy()
  })

  it('管理员额外显示管理员标记', () => {
    mockedUseAuth.mockReturnValue({
      user: { id: 1, username: 'boss', is_admin: true },
      isAdmin: true,
      loading: false,
      login: vi.fn(),
      logout: logoutMock,
    })
    renderPage()
    expect(screen.getByText(/当前账号：boss（管理员）/)).toBeTruthy()
  })

  it('新密码少于 6 位时本地拦截', async () => {
    const { container } = renderPage()
    fill(container, 'old123', '123', '123')
    fireEvent.submit(container.querySelector('form')!)

    await waitFor(() => expect(screen.getByText('新密码至少 6 位')).toBeTruthy())
    expect(changePasswordMock).not.toHaveBeenCalled()
  })

  it('两次新密码不一致时本地拦截', async () => {
    const { container } = renderPage()
    fill(container, 'old123', 'abc123', 'abc124')
    fireEvent.submit(container.querySelector('form')!)

    await waitFor(() => expect(screen.getByText('两次输入的新密码不一致')).toBeTruthy())
    expect(changePasswordMock).not.toHaveBeenCalled()
  })

  it('修改成功后提示成功并清空输入', async () => {
    changePasswordMock.mockResolvedValue({})
    const { container } = renderPage()
    fill(container, 'old123', 'new123', 'new123')
    fireEvent.submit(container.querySelector('form')!)

    await waitFor(() => expect(screen.getByText('密码修改成功')).toBeTruthy())
    const pwds = container.querySelectorAll<HTMLInputElement>('input[type="password"]')
    expect(pwds[0].value).toBe('')
  })

  it('后端报错时展示错误信息', async () => {
    changePasswordMock.mockRejectedValue(apiError('原密码错误', 400))
    const { container } = renderPage()
    fill(container, 'wrong', 'new123', 'new123')
    fireEvent.submit(container.querySelector('form')!)

    await waitFor(() => expect(screen.getByText('原密码错误')).toBeTruthy())
  })

  it('点击退出登录会清空登录态并跳转登录页', async () => {
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: '退出登录' }))

    expect(logoutMock).toHaveBeenCalled()
    await waitFor(() => expect(screen.getByText('登录页')).toBeTruthy())
  })
})