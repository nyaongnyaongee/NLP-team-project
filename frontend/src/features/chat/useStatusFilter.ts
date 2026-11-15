import { useState } from 'react'
import type { Conversation } from '../../api/types'

export type ConversationStatus = 'open' | 'closed'

// 대화 목록을 「대화 중」 / 「종료된 대화」로 나눠 본다 (교사·학부모 공용).
export function useStatusFilter(conversations: Conversation[]) {
  const [show, setShow] = useState<ConversationStatus>('open')
  const openCount = conversations.filter((c) => c.status !== 'closed').length
  const shown = conversations.filter((c) => (show === 'closed') === (c.status === 'closed'))
  return { show, setShow, shown, openCount, closedCount: conversations.length - openCount }
}
