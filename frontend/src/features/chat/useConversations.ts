import { useCallback } from 'react'
import { listConversations } from '../../api/conversations'
import type { Conversation } from '../../api/types'
import { useSync } from '../../realtime/useSync'
import { useResource } from './useResource'

const NONE: Conversation[] = []

// 내 대화 목록. 대화 알림이 오면 다시 읽는다 (상대가 새 대화를 열었을 때, 마지막 메시지 시각 · 순서가 바뀔 때).
export function useConversations() {
  const { data, setData, loaded, error, refresh } = useResource(listConversations, NONE)
  useSync('conversations', refresh, (e) => e.type === 'changed')

  // 방금 시작한 대화를 목록에 넣는다 (이미 있으면 그대로)
  const add = useCallback(
    (c: Conversation) => setData((prev) => (prev.some((p) => p.id === c.id) ? prev : [...prev, c])),
    [setData],
  )
  return { conversations: data, loading: !loaded && error === null, error, add }
}
