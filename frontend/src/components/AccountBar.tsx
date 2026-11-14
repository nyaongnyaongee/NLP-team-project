import { useAuth } from '../auth/AuthContext'
import { ROLE_LABEL } from '../auth/roles'

// 상단 바 아래줄: 사용자 이름·역할과 로그아웃 (데모의 .topline 자리). 데모에 로그아웃은 없어 알림 토글과 같은 알약 모양을 쓴다.
export default function AccountBar() {
  const { session, logout } = useAuth()
  if (!session) return null
  return (
    <div className="topline">
      <span className="who">
        {session.name} ({ROLE_LABEL[session.role]})
      </span>
      <button type="button" className="notification-toggle off" onClick={logout}>
        로그아웃
      </button>
    </div>
  )
}
