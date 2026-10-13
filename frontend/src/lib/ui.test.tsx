import { describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { UiProvider, useUi } from './ui'

function Probe() {
  const { toast, confirm } = useUi()
  return (
    <div>
      <button onClick={() => toast('保存成功', 'success')}>成功提示</button>
      <button onClick={() => toast('出错了', 'error')}>错误提示</button>
      <button
        onClick={async () => {
          const ok = await confirm('确定删除吗？')
          toast(ok ? '已删除' : '已取消')
        }}
      >
        触发确认
      </button>
    </div>
  )
}

function renderProbe() {
  return render(
    <UiProvider>
      <Probe />
    </UiProvider>,
  )
}

describe('UiProvider', () => {
  it('toast 展示提示文案', async () => {
    renderProbe()
    fireEvent.click(screen.getByRole('button', { name: '成功提示' }))
    expect(await screen.findByText('保存成功')).toBeTruthy()
  })

  it('toast 一段时间后自动消失', () => {
    vi.useFakeTimers()
    try {
      renderProbe()
      fireEvent.click(screen.getByRole('button', { name: '错误提示' }))
      expect(screen.getByText('出错了')).toBeTruthy()

      // 假定时器下不能用 waitFor（它靠真实定时器轮询，会一直等下去）
      act(() => {
        vi.advanceTimersByTime(3100)
      })
      expect(screen.queryByText('出错了')).toBeNull()
    } finally {
      vi.useRealTimers()
    }
  })

  it('确认框点「确定」返回 true', async () => {
    renderProbe()
    fireEvent.click(screen.getByRole('button', { name: '触发确认' }))
    expect(await screen.findByRole('dialog')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: '确定' }))
    expect(await screen.findByText('已删除')).toBeTruthy()
  })

  it('确认框点「取消」返回 false', async () => {
    renderProbe()
    fireEvent.click(screen.getByRole('button', { name: '触发确认' }))
    await screen.findByRole('dialog')

    fireEvent.click(screen.getByRole('button', { name: '取消' }))
    expect(await screen.findByText('已取消')).toBeTruthy()
  })

  it('在 UiProvider 之外使用会抛错', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => render(<Probe />)).toThrow('useUi 必须在 UiProvider 内使用')
    spy.mockRestore()
  })
})