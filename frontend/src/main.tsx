import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
// 디자인: 데모의 CSS 를 수정 없이 복사한 두 파일 + 앱 전용 보정 (S8). 폰트 파일 위치는 src/design/fonts/README.md
import './design/sky-tokens.css'
import './design/sky-app.css'
import './design/app-layout.css'
import './design/ios-polish.css' // iOS 느낌 다듬기 (색 · 모양만, 빼면 예전 모양)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
