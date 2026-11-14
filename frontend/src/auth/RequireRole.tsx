import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import type { Role } from '../api/types'
import { useAuth } from './AuthContext'
import { HOME_PATH } from './roles'

// 로그인 안 함 → /login, 다른 역할의 주소 → 자기 시작 화면.
// 서버가 최종 권한 검사를 하므로 이것은 화면 안내용이다.
export default function RequireRole({ role, children }: { role: Role; children: ReactNode }) {
  const { session } = useAuth()
  if (!session) return <Navigate to="/login" replace />
  if (session.role !== role) return <Navigate to={HOME_PATH[session.role]} replace />
  return <>{children}</>
}
