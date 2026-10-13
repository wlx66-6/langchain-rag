import { fireEvent, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Route, Routes } from 'react-router-dom'
import LoginPage from './LoginPage'
import { useAuth } from '../lib/auth'
import { apiError } from '../test/fixtures'
import { renderWithProviders } from '../test/render'

vi.mock('../lib/auth', () => ({ useAuth: vi.fn() }))

const mockedUseAuth = vi.mocked(useAuth)
const loginMock = vi.fn()

function renderPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/chat" element={<div>聊天页</div>} />
    </Routes>,
    '/login',
  )
}

function fill(container: HTMLElement, username: string, password: string) {
  fireEvent.change(screen.getByRole('textbox'), { target: { value: username } })
  fireEvent.change(container.querySelector('input[type="password"]')!, {
    target: { value: password },
  })
}

function submit(container: HTMLElement) {
  fireEvent.submit(container.querySelector('form')!)
}

beforeEach(() => {
  loginMock.mockReset()
  mockedUseAuth.mockReturnValue({
    user: null,
    isAdmin: false,
    loading: false,
    login: loginMock,
    logout: vi.fn(),
  })
})

describe('LoginPage', () => {
  it('渲染标题与登录表单', () => {
    renderPage()
    expect(screen.getByText('电商知识库问答系统')).toBeTruthy()
    expect(screen.getByRole('button', { name: '登录' })).toBeTruthy()
  })

  it('登录成功后跳转到聊天页', async () => {
    loginMock.mockResolvedValue(undefined)
    const { container } = renderPage()
    fill(container, '  alice  ', 'secret123')
    submit(container)

    await waitFor(() => expect(screen.getByText('聊天页')).toBeTruthy())
    // 用户名两侧空白会被去掉后再提交
    expect(loginMock).toHaveBeenCalledWith('alice', 'secret123')
  })

  it('登录失败时展示后端返回的错误信息', async () => {
    loginMock.mockRejectedValue(apiError('用户名或密码错误', 401))
    const { container } = renderPage()
    fill(container, 'alice', 'wrong')
    submit(container)

    await waitFor(() => expect(screen.getByText('用户名或密码错误')).toBeTruthy())
  })

  it('登录失败且后端无 detail 时展示兜底文案', async () => {
    loginMock.mockRejectedValue({ weird: true })
    const { container } = renderPage()
    fill(container, 'alice', 'secret123')
    submit(container)

    await waitFor(() => expect(screen.getByText('登录失败，请重试')).toBeTruthy())
  })

  it('登录请求进行中时按钮显示加载态并禁用', async () => {
    let resolveLogin: () => void = () => {}
    loginMock.mockImplementation(() => new Promise<void>((r) => (resolveLogin = r)))
    const { container } = renderPage()
    fill(container, 'alice', 'secret123')
    submit(container)

    await waitFor(() => expect(screen.getByText('登录中…')).toBeTruthy())
    expect((screen.getByRole('button') as HTMLButtonElement).disabled).toBe(true)

    // 登录完成后跳转到聊天页，加载态随之结束
    resolveLogin()
    await waitFor(() => expect(screen.getByText('聊天页')).toBeTruthy())
  })
})
