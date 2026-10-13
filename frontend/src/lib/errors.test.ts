import { describe, expect, it } from 'vitest'
import { errorMessage } from './errors'
import { apiError } from '../test/fixtures'

describe('errorMessage', () => {
  it('axios 错误优先使用后端返回的 detail', () => {
    expect(errorMessage(apiError('用户名已被占用'), '兜底文案')).toBe('用户名已被占用')
  })

  it('axios 错误但没有 detail 时用兜底文案', () => {
    const err = Object.assign(new Error('boom'), { isAxiosError: true, response: { status: 500 } })
    expect(errorMessage(err, '操作失败')).toBe('操作失败')
  })

  it('请求没发出去（无 response）时提示检查后端', () => {
    const err = Object.assign(new Error('Network Error'), { isAxiosError: true })
    expect(errorMessage(err, '操作失败')).toBe('网络异常，请确认后端服务已启动')
  })

  it('普通 Error 使用其 message', () => {
    expect(errorMessage(new Error('模型炸了'), '兜底')).toBe('模型炸了')
  })

  it('非 Error 类型一律回退到兜底文案', () => {
    expect(errorMessage('字符串异常', '兜底')).toBe('兜底')
    expect(errorMessage(null, '兜底')).toBe('兜底')
    expect(errorMessage(undefined, '兜底')).toBe('兜底')
  })
})