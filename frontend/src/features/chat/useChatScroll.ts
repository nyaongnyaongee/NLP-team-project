import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { Message } from '../../api/types'

const NEAR_BOTTOM = 80 // 맨 아래에서 이 안(px)이면 「아래를 보는 중」으로 본다

const reduceMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true

// 채팅 하단 자동 스크롤 (교사 · 학부모 대화방 공용). 스크롤하는 곳은 컴포넌트 밖의 .content 이므로 logRef 로 찾아간다.
//  - 대화를 열면 맨 아래로 (바로)
//  - 새 메시지(마지막 번호가 커진 때만 — 정제가 끝나 높이만 바뀐 것은 제외):
//      내가 보낸 글 → 항상 맨 아래로 / 상대 글 → 아래를 보는 중이면 맨 아래로, 위를 보는 중이면 이동하지 않고 showNew 를 켠다
//  - 맨 아래에 닿거나 scrollToBottom 을 부르면 showNew 가 꺼진다
export function useChatScroll(messages: Message[], isMine: (m: Message) => boolean) {
  const logRef = useRef<HTMLUListElement>(null)
  const [showNew, setShowNew] = useState(false)
  const lastIdRef = useRef<number | null>(null)
  const isMineRef = useRef(isMine)
  useEffect(() => {
    isMineRef.current = isMine
  })

  const scroller = () => logRef.current?.closest<HTMLElement>('.content') ?? null
  const distanceFromBottom = (el: HTMLElement) => el.scrollHeight - el.scrollTop - el.clientHeight

  const scrollToBottom = useCallback((smooth = true) => {
    const el = logRef.current?.closest<HTMLElement>('.content')
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: smooth && !reduceMotion() ? 'smooth' : 'auto' })
    setShowNew(false)
  }, [])

  // 사용자가 직접 맨 아래까지 내려오면 버튼을 지운다
  useEffect(() => {
    const el = logRef.current?.closest<HTMLElement>('.content')
    if (!el) return
    const onScroll = () => {
      if (el.scrollHeight - el.scrollTop - el.clientHeight <= NEAR_BOTTOM) setShowNew(false)
    }
    el.addEventListener('scroll', onScroll, { passive: true })
    return () => el.removeEventListener('scroll', onScroll)
  }, [])

  useLayoutEffect(() => {
    if (messages.length === 0) return
    const lastId = Math.max(...messages.map((m) => m.id))
    const prev = lastIdRef.current
    lastIdRef.current = lastId
    if (prev === null) {
      scrollToBottom(false) // 처음 열림
      return
    }
    if (lastId <= prev) return
    const fresh = messages.filter((m) => m.id > prev)
    const el = scroller()
    if (fresh.some((m) => isMineRef.current(m)) || (el && distanceFromBottom(el) <= NEAR_BOTTOM)) scrollToBottom()
    else setShowNew(true)
  }, [messages, scrollToBottom])

  return { logRef, showNew, scrollToBottom }
}
