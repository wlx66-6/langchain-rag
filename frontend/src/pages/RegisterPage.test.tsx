import { fireEvent, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Route, Routes } from 'react-router-dom'
import RegisterPage from './RegisterPage'
import { authApi } from '../lib/api'
import { apiError } from '../test/fixtures'
import { renderWithProviders } from '../test/render'

vi.mock('../lib/api', () => ({
  authApi: { register: vi.fn() },
}))

const registerMock = vi.mocked(authApi.register)

function renderPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/login" element={<div>登录页</div>} />
    </Routes>,
    '/register',
  )
}

function fill(container: HTMLElement, username: string, password: string, confirm: string) {
  fireEvent.change(screen.getByRole('textbox'), { target: { value: username } })
  const pwds = container.querySelectorAll('input[type="password"]')
  fireEvent.change(pwds[0], { target: { value: password } })
  fireEvent.change(pwds[1], { target: { value: confirm } })
}

function submit(container: HTMLElement) {
  fireEvent.submit(container.querySelector('form')!)
}

beforeEach(() => {
  registerMock.mockReset()
})

describe('RegisterPage', () => {
  it('密码少于 6 位时本地拦截，不发起请求', async () => {
    const { container } = renderPage()
    fill(container, 'newbie', '123', '123')
    submit(container)

    await waitFor(() => expect(screen.getByText('密码至少 6 位')).toBeTruthy())
    expect(registerMock).not.toHaveBeenCalled()
  })

  it('两次密码不一致时本地拦截', async () => {
    const { container } = renderPage()
    fill(container, 'newbie', 'abc123', 'abc124')
    submit(container)

    await waitFor(() => expect(screen.getByText('两次输入的密码不一致')).toBeTruthy())
    expect(registerMock).not.toHaveBeenCalled()
  })

  it('注册成功后跳转到登录页并提示成功', async () => {
    registerMock.mockResolvedValue({})
    const { container } = renderPage()
    fill(container, 'newbie', 'abc123', 'abc123')
    submit(container)

    await waitFor(() => expect(screen.getByText('登录页')).toBeTruthy())
    expect(registerMock).toHaveBeenCalledWith('newbie', 'abc123')
    expect(await screen.findByText('注册成功，请登录')).toBeTruthy()
  })

  it('用户名为空时本地拦截', async () => {
    const { container } = renderPage()
    fill(container, '   ', 'abc123', 'abc123')
    submit(container)

    await waitFor(() => expect(screen.getByText('请输入用户名')).toBeTruthy())
    expect(registerMock).not.toHaveBeenCalled()
  })

  it('后端返回用户名占用时展示错误', async () => {
    registerMock.mockRejectedValue(apiError('用户名已被占用', 400))
    const { container } = renderPage()
    fill(container, 'exists', 'abc123', 'abc123')
    submit(container)

    await waitFor(() => expect(screen.getByText('用户名已被占用')).toBeTruthy())
  })

  it('无法识别的异常展示兜底文案', async () => {
    registerMock.mockRejectedValue({ weird: true })
    const { container } = renderPage()
    fill(container, 'newbie', 'abc123', 'abc123')
    submit(container)

    await waitFor(() => expect(screen.getByText('注册失败，请重试')).toBeTruthy())
  })

  it('普通异常直接展示其 message', async () => {
    registerMock.mockRejectedValue(new Error('boom'))
    const { container } = renderPage()
    fill(container, 'newbie', 'abc123', 'abc123')
    submit(container)

    await waitFor(() => expect(screen.getByText('boom')).toBeTruthy())
  })
})