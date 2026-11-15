import { readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'

// 서비스워커 캐시 이름에 빌드 시각을 넣는다: 새 빌드마다 옛 앱 셸 캐시가 정리된다.
// 치환이 안 되면(자리표시자가 남으면) 옛 캐시가 영영 안 지워지므로 빌드를 실패시킨다.
function swBuildId(): Plugin {
  let outDir = 'dist'
  let root = process.cwd()
  return {
    name: 'ieum-sw-build-id',
    apply: 'build',
    configResolved(config) {
      outDir = config.build.outDir
      root = config.root
    },
    closeBundle() {
      const file = resolve(root, outDir, 'sw.js')
      const src = readFileSync(file, 'utf-8')
      const out = src.replaceAll('__BUILD_ID__', new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 14))
      if (out.includes('__BUILD_ID__')) throw new Error('dist/sw.js 의 __BUILD_ID__ 치환 실패')
      writeFileSync(file, out)
    },
  }
}

// 명세 4.2: 브라우저는 /api 로만 요청하고, 개발 서버가 백엔드(8000)로 전달한다.
// 같은 출처로 보이므로 서버의 CORS 설정을 바꿀 필요가 없다.
export default defineConfig({
  plugins: [react(), swBuildId()],
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
