import { useEffect } from 'react'
import { markRead } from '../../api/conversations'
import type { Message } from '../../api/types'

// 대화방을 보고 있는 동안 새 메시지가 보이면 읽음으로 알린다 (목록의 빨간 숫자가 0 이 된다).
// 탭이 숨겨져 있을 때는 읽은 것이 아니므로 기다렸다가, 다시 보이면 알린다. 실패해도 화면은 그대로 둔다.
export function useMarkRead(conversationId: number, messages: Message[]) {
  const lastId = messages.length ? messages[messages.length - 1].id : null
  useEffect(() => {
    if (lastId === null) return
    const send = () => {
      if (!document.hidden) void markRead(conversationId).catch(() => {})
    }
    send()
    document.addEventListener('visibilitychange', send)
    return () => document.removeEventListener('visibilitychange', send)
  }, [conversationId, lastId])
}
