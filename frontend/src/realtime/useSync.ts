import { useEffect, useRef } from 'react'
import type { ServerEvent } from '../api/ws'
import { useRealtimeHub } from './RealtimeContext'

const POLL_MS = 2000 // 명세 8장

// 화면의 데이터를 최신으로 유지한다.
//  - 알림 연결이 있으면: matches 에 해당하는 알림이 올 때만 refresh 한다. 폴링은 멈춘다.
//  - 연결이 없거나 끊기면: 2초마다 refresh 한다 (폴링). 연결이 복구되면 폴링을 멈춘다.
//  - 탭이 숨겨지면 폴링을 멈추고, 다시 보이면 바로 한 번 읽고 재개한다.
// 무엇을 읽을지는 refresh 가 정한다 (알림이든 폴링이든 내용은 항상 GET 으로 다시 받는다).
// key 가 바뀌면 (예: 다른 대화) 처음부터 다시 구독한다.
export function useSync(key: unknown, refresh: () => void, matches: (event: ServerEvent) => boolean) {
  const hub = useRealtimeHub()

  const refreshRef = useRef(refresh)
  const matchesRef = useRef(matches)
  useEffect(() => {
    refreshRef.current = refresh
    matchesRef.current = matches
  })

  useEffect(() => {
    let pollTimer: number | undefined

    const syncPolling = () => {
      const shouldPoll = !document.hidden && !hub.isReady()
      if (shouldPoll && pollTimer === undefined) {
        pollTimer = window.setInterval(() => refreshRef.current(), POLL_MS)
      } else if (!shouldPoll && pollTimer !== undefined) {
        window.clearInterval(pollTimer)
        pollTimer = undefined
      }
    }

    const offReady = hub.onReadyChange((ready) => {
      syncPolling()
      if (ready) refreshRef.current() // 연결 전에 놓친 변화를 한 번 받아 온다
    })
    const offEvent = hub.subscribe((event) => {
      // 숨겨진 탭은 다시 보일 때 읽는다
      if (!document.hidden && matchesRef.current(event)) refreshRef.current()
    })
    const onVisibility = () => {
      syncPolling()
      if (!document.hidden) refreshRef.current()
    }

    syncPolling()
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      if (pollTimer !== undefined) window.clearInterval(pollTimer)
      offReady()
      offEvent()
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [hub, key])
}
