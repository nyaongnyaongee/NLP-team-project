import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { joinWithCode, login as loginApi } from '../api/auth'
import { setUnauthorizedHandler } from '../api/client'
import { saveScenarioId } from '../features/demo/scenarios'
import { clearSession, loadSession, saveSession, type Session } from './authStorage'

type AuthValue = {
  session: Session | null
  login: (loginId: string, password: string) => Promise<void>
  join: (inviteCode: string, studentName: string, parentName: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  // 새로고침 후 복구: 처음 그릴 때 sessionStorage 에서 읽는다.
  const [session, setSession] = useState<Session | null>(() => loadSession())

  const logout = useCallback(() => {
    clearSession()
    setSession(null)
    // 방어적: 앱 셸 캐시에는 사용자 데이터가 없지만, 로그아웃하면 Cache Storage 를 전부 비운다. 실패해도 로그아웃은 막지 않는다.
    if (typeof caches !== 'undefined') {
      caches
        .keys()
        .then((keys) => Promise.all(keys.map((k) => caches.delete(k))))
        .catch(() => {})
    }
  }, [])

  const login = useCallback(async (loginId: string, password: string) => {
    const res = await loginApi(loginId, password)
    saveScenarioId(null) // 시연 역할 카드는 손님(시연 QR)만. 시험하다 남은 카드를 지운다
    const next: Session = { token: res.token, name: res.name, role: res.role }
    saveSession(next)
    setSession(next)
  }, [])

  const join = useCallback(async (inviteCode: string, studentName: string, parentName: string) => {
    const res = await joinWithCode(inviteCode, studentName, parentName)
    const next: Session = { token: res.token, name: res.name, role: res.role, guest: true }
    saveSession(next)
    setSession(next)
  }, [])

  // client.ts 가 401 을 받으면 로그아웃 처리 (명세 3.1)
  useEffect(() => {
    setUnauthorizedHandler(logout)
    return () => setUnauthorizedHandler(null)
  }, [logout])

  const value = useMemo(() => ({ session, login, join, logout }), [session, login, join, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth 는 AuthProvider 안에서만 쓸 수 있습니다')
  return ctx
}
