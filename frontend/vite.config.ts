import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 前端所有以 /api 开头的请求，都转发到后端 8000 端口
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
