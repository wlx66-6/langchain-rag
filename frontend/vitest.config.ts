import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Vitest 测试配置：复用 Vite 的 React 插件，测试环境用 jsdom（提供 DOM 和 localStorage）
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    // 每个用例结束后自动卸载组件，避免 DOM 叠加
    setupFiles: ['./src/test/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      include: ['src/**/*.{ts,tsx}'],
      // types.ts 只有类型声明、没有可执行代码，统计进来只会拉低数字
      exclude: [
        'src/**/*.test.{ts,tsx}',
        'src/main.tsx',
        'src/test/**',
        'src/lib/types.ts',
      ],
      // 覆盖率门槛：低于该值 vitest 直接失败，防止覆盖率回退
      thresholds: { lines: 60, functions: 60, branches: 60, statements: 60 },
    },
  },
})