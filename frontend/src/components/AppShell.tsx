import type { ReactNode } from 'react'
import logo from '../design/ieum-logo.png'
import AccountBar from './AccountBar'

// 데모(app-sage.html)에 적힌 학교 이름. 서버에 학교 정보가 없어 데모 문구를 그대로 쓴다 (B1 참고).
const SCHOOL_NAME = '숭실초등학교'

// 모든 화면의 틀: 위 바(로고·학교·계정), 가운데 내용(.content 만 스크롤), 아래 탭(nav, 선택).
// 데모의 기기 모형 장식(상태 표시줄, 홈 바, 노치)은 가져오지 않았다.
export default function AppShell({
  title,
  nav,
  children,
}: {
  title: string // 화면에는 보이지 않는 제목 (문서 구조·스크린 리더용)
  nav?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="stage">
      <div className="phone-shell">
        <section className="phone" aria-label="이음">
          <header className="top">
            <div className="brand-row">
              <div className="brand">
                <span className="logo-lockup ieum-lockup" role="img" aria-label="이음">
                  <img className="ieum-art" src={logo} alt="" width={216} height={130} />
                </span>
              </div>
              <span className="school-name">{SCHOOL_NAME}</span>
            </div>
            <AccountBar />
          </header>
          <main className="content">
            <h1 className="sr-only">{title}</h1>
            {children}
          </main>
          {nav}
        </section>
      </div>
    </div>
  )
}
