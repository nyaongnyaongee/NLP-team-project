import { useCallback, useEffect, useRef, useState } from 'react'

// 초안 요청 하나의 상태: 만드는 중(몇 초 걸린다), 오류 문장(detail 그대로), 연타 방지.
// 실패해도 화면은 그대로이고, 같은 버튼으로 다시 시도할 수 있다. 화면을 떠난 뒤 늦게 온 결과는 버린다.
export function useDraftRequest() {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const aliveRef = useRef(true)
  const busyRef = useRef(false)

  useEffect(() => {
    aliveRef.current = true
    return () => {
      aliveRef.current = false
    }
  }, [])

  // 성공하면 결과를, 실패하거나 이미 진행 중이거나 화면을 떠났으면 null 을 돌려준다.
  const run = useCallback(async <T>(call: () => Promise<T>): Promise<T | null> => {
    if (busyRef.current) return null
    busyRef.current = true
    setPending(true)
    setError(null)
    try {
      const result = await call()
      return aliveRef.current ? result : null
    } catch (e) {
      if (aliveRef.current) setError(e instanceof Error ? e.message : '초안을 만들지 못했습니다')
      return null
    } finally {
      busyRef.current = false
      if (aliveRef.current) setPending(false)
    }
  }, [])

  return { pending, error, run }
}
