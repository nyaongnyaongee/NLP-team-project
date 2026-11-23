import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
// 디자인: 데모의 CSS 를 수정 없이 복사한 두 파일 + 앱 전용 보정 (S8). 폰트 파일 위치는 src/design/fonts/README.md
import './design/sky-tokens.css'
import './design/sky-app.css'
import './design/app-layout.css'
import './design/ios-polish.css' // iOS 느낌 다듬기 (색 · 모양만, 빼면 예전 모양)
import './design/look.css' // 시안 느낌 (큰 로고 머리 · 메시지 작성 · 교사 인사 · 배지 탭)
import './design/home-clean.css' // 대화 목록 첫 화면 정리 (인사 한 줄 · 숫자 띠 · 묶은 목록)

// 서비스워커(앱 셸 캐시): 운영 빌드에서만 등록한다. 개발 중 옛 화면이 남지 않게. 실패해도 앱에는 영향 없다.
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {})
  })
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
