import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useAuth } from '../auth/AuthContext'
import logo from '../design/ieum-logo.png'
import { useRealtimeHub } from '../realtime/RealtimeContext'
import AccountBar from './AccountBar'
import { RefreshIcon } from './icons'
import { useScrollRestoration } from './useScrollRestoration'

// 데모(app-sage.html)에 적힌 학교 이름. 서버에 학교 정보가 없어 데모 문구를 그대로 쓴다 (B1 참고).
export const SCHOOL_NAME = '숭실초등학교'

const WHO: Record<string, (name: string) => string> = {
  parent: (n) => `학부모 전용 · ${n} 학부모`,
  teacher: (n) => `교사 전용 · ${n} 선생님`,
  complaint_team: (n) => `민원담당자 전용 · ${n}`,
}

// 실시간 알림 연결 상태 (교사 화면 「알림 ON」). 끊기면 화면은 2초마다 다시 읽는다
function LiveBadge() {
  const hub = useRealtimeHub()
  const [ready, setReady] = useState(() => hub.isReady())
  useEffect(() => hub.onReadyChange(setReady), [hub])
  return (
    <span className={`live-badge${ready ? '' : ' off'}`} title={ready ? '새 메시지를 바로 받아요' : '연결 중 — 잠시마다 새로 읽어요'}>
      알림 {ready ? 'ON' : 'OFF'}
    </span>
  )
}

// 모든 화면의 틀: 위 머리(큰 로고 · 학교, 그 아래 「누구 전용 · 이름」 · 알림 · 새로고침 · 프로필), 가운데 내용(.content 만 스크롤), 아래 탭(nav, 선택).
export default function AppShell({
  title,
  nav,
  children,
}: {
  title: string // 화면에는 보이지 않는 제목 (문서 구조·스크린 리더용)
  nav?: ReactNode
  children: ReactNode
}) {
  const { session } = useAuth()
  const contentRef = useRef<HTMLElement>(null)
  useScrollRestoration(contentRef) // 하위 화면에서 돌아오면 이전 스크롤 위치로, 그 밖의 이동은 맨 위에서 시작
  return (
    <div className="stage">
      <div className="phone-shell">
        <section className="phone" aria-label="이음">
          <header className="top masthead">
            <div className="brand-row">
              <div className="brand">
                <span className="logo-lockup ieum-lockup" role="img" aria-label="이음">
                  <img className="ieum-art" src={logo} alt="" width={216} height={130} />
                </span>
              </div>
              <span className="school-name">{SCHOOL_NAME}</span>
            </div>
            {session && (
              <div className="topline">
                <span className="who">{(WHO[session.role] ?? ((n: string) => n))(session.name)}</span>
                {session.role === 'teacher' && <LiveBadge />}
                <button type="button" className="reset" onClick={() => window.location.reload()} aria-label="새로고침">
                  <RefreshIcon />
                </button>
                <AccountBar school={SCHOOL_NAME} />
              </div>
            )}
          </header>
          <main className="content" ref={contentRef}>
            <h1 className="sr-only">{title}</h1>
            {children}
          </main>
          {nav}
        </section>
      </div>
    </div>
  )
}
