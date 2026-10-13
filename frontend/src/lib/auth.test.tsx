import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { useAuth } from './auth'

function Probe() {
  useAuth()
  return null
}

describe('useAuth', () => {
  it('在 AuthProvider 之外使用会抛错', () => {
    expect(() => render(<Probe />)).toThrow('useAuth 必须在 AuthProvider 内使用')
  })
})
