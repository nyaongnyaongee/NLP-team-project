import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { useAuth } from '../auth/AuthContext'
import { RealtimeHub } from './RealtimeHub'

const RealtimeContext = createContext<RealtimeHub | null>(null)

// 로그인한 동안 알림 연결을 연다. 로그아웃(토큰이 없어짐)하면 닫는다.
export function RealtimeProvider({ children }: { children: ReactNode }) {
  const { session } = useAuth()
  const token = session?.token ?? null
  const [hub] = useState(() => new RealtimeHub())

  useEffect(() => {
    if (token === null) return
    hub.connect(token)
    return () => hub.disconnect()
  }, [hub, token])

  return <RealtimeContext.Provider value={hub}>{children}</RealtimeContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useRealtimeHub(): RealtimeHub {
  const hub = useContext(RealtimeContext)
  if (!hub) throw new Error('useRealtimeHub 는 RealtimeProvider 안에서만 쓸 수 있습니다')
  return hub
}
