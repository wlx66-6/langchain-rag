// Vitest 全局测试初始化。
// 未开启 globals 时，@testing-library/react 不会自动注册 afterEach 清理，
// 导致多个用例的 DOM 叠加、查询到重复元素。这里显式挂上 cleanup。
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => {
  cleanup()
})

// jsdom 没有实现 scrollIntoView，聊天页自动滚动到底部时会报错，这里补一个空实现
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {}
}
