import { beforeEach, describe, expect, it } from 'vitest'
import { clearTokens, getAccessToken, setTokens } from './api'

describe('令牌存取', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('初始时没有令牌', () => {
    expect(getAccessToken()).toBeNull()
  })

  it('setTokens 后能取到 access_token，refresh_token 也写入', () => {
    setTokens('access-abc', 'refresh-xyz')
    expect(getAccessToken()).toBe('access-abc')
    expect(localStorage.getItem('refresh_token')).toBe('refresh-xyz')
  })

  it('clearTokens 清空令牌和用户信息', () => {
    setTokens('access-abc', 'refresh-xyz')
    localStorage.setItem('user', '{"id":1}')
    clearTokens()
    expect(getAccessToken()).toBeNull()
    expect(localStorage.getItem('refresh_token')).toBeNull()
    expect(localStorage.getItem('user')).toBeNull()
  })
})