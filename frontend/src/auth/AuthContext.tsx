import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { login as loginApi } from '../api/auth'
import { setUnauthorizedHandler } from '../api/client'
import { clearSession, loadSession, saveSession, type Session } from './authStorage'

type AuthValue = {
  session: Session | null
  login: (loginId: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  // 새로고침 후 복구: 처음 그릴 때 sessionStorage 에서 읽는다.
  const [session, setSession] = useState<Session | null>(() => loadSession())

  const logout = useCallback(() => {
    clearSession()
    setSession(null)
  }, [])

  const login = useCallback(async (loginId: string, password: string) => {
    const res = await loginApi(loginId, password)
    const next: Session = { token: res.token, name: res.name, role: res.role }
    saveSession(next)
    setSession(next)
  }, [])

  // client.ts 가 401 을 받으면 로그아웃 처리 (명세 3.1)
  useEffect(() => {
    setUnauthorizedHandler(logout)
    return () => setUnauthorizedHandler(null)
  }, [logout])

  const value = useMemo(() => ({ session, login, logout }), [session, login, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth 는 AuthProvider 안에서만 쓸 수 있습니다')
  return ctx
}
