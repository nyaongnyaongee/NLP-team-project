import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// 명세 4.2: 브라우저는 /api 로만 요청하고, 개발 서버가 백엔드(8000)로 전달한다.
// 같은 출처로 보이므로 서버의 CORS 설정을 바꿀 필요가 없다.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174, // dev.py 확인 화면이 5173을 쓰므로 겹치지 않게
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true, // WebSocket(/api/ws)도 전달
        rewrite: (p) => p.replace(/^\/api/, ''),
      },
    },
  },
})
