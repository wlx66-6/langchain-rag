import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Vitest 测试配置：复用 Vite 的 React 插件，测试环境用 jsdom（提供 DOM 和 localStorage）
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
  },
})