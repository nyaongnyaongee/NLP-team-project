import { useEffect, useRef, useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import { ROLE_LABEL } from '../auth/roles'

// 오른쪽 위 동그란 프로필 단추 (iOS 앱처럼). 누르면 이름 · 역할 · 학교와 로그아웃이 나온다.
export default function AccountBar({ school }: { school: string }) {
  const { session, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === 'Escape' : !box.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', close)
    }
  }, [open])

  if (!session) return null
  return (
    <div className="profile" ref={box}>
      <button
        type="button"
        className="profile-button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={`${session.name} (${ROLE_LABEL[session.role]}) 계정`}
      >
        {session.name.slice(0, 1)}
      </button>
      {open && (
        <div className="profile-menu" role="menu">
          <div className="profile-who">
            <b>{session.name}</b>
            <small>
              {ROLE_LABEL[session.role]} · {school}
            </small>
          </div>
          <button type="button" role="menuitem" className="profile-logout" onClick={logout}>
            로그아웃
          </button>
        </div>
      )}
    </div>
  )
}
