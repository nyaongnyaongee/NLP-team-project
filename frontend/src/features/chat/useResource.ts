import { useCallback, useEffect, useRef, useState } from 'react'

// 서버에서 읽어 오는 값 하나(메시지 목록, 대화 정보 등)를 들고 있는다. 다시 읽는 시점은 realtime/useConversationSync 가 정한다.
// load 는 useCallback 으로 고정된 함수여야 한다 (바뀌면 새로 읽는다).
export function useResource<T>(load: () => Promise<T>, initial: T) {
  const [data, setData] = useState<T>(initial)
  const [loaded, setLoaded] = useState(false) // 첫 조회가 끝났는지 (이후 갱신 중에는 "불러오는 중"을 띄우지 않는다)
  const [error, setError] = useState<string | null>(null)

  const aliveRef = useRef(true)
  const inFlightRef = useRef(false)
  const againRef = useRef(false)

  // 조회는 한 번에 하나만 하고, 도중에 또 요청이 오면 끝난 뒤 한 번 더 한다
  // (알림이 조회 도중에 와도 그 변화를 놓치지 않고, 오래된 응답이 새 응답을 덮어쓰지도 않는다).
  const refresh = useCallback(async function run(): Promise<void> {
    if (inFlightRef.current) {
      againRef.current = true
      return
    }
    inFlightRef.current = true
    try {
      const value = await load()
      if (!aliveRef.current) return
      setData(value)
      setError(null)
    } catch (e) {
      if (aliveRef.current) setError(e instanceof Error ? e.message : '불러오지 못했습니다') // 값은 그대로 둔다
    } finally {
      inFlightRef.current = false
      if (aliveRef.current) {
        setLoaded(true)
        if (againRef.current) {
          againRef.current = false
          void run()
        }
      }
    }
  }, [load])

  useEffect(() => {
    aliveRef.current = true
    againRef.current = false
    // 첫 조회: 서버와 동기화하는 effect 이고, setState 는 응답을 받은 뒤(비동기)에만 일어난다.
    // oxlint-disable-next-line react/set-state-in-effect
    void refresh()
    return () => {
      aliveRef.current = false
    }
  }, [refresh])

  return { data, setData, loaded, error, refresh }
}
