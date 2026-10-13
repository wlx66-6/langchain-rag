import { render } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { UiProvider } from '../lib/ui'

/**
 * 渲染页面并套上测试需要的 Provider（路由 + 交互反馈）。
 * 页面组件平时从 App 里拿到这两个 Provider，单测里单独渲染时要自己补上。
 */
export function renderWithProviders(children: ReactNode, route = '/') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <UiProvider>{children}</UiProvider>
    </MemoryRouter>,
  )
}
