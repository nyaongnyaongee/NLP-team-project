import { useCallback } from 'react'
import { deleteConversation, listConversations } from '../../api/conversations'
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
  // 지운 대화를 목록에서 뺀다
  const remove = useCallback((id: number) => setData((prev) => prev.filter((p) => p.id !== id)), [setData])
  // 내 목록에서 지운다 (종료된 대화만, DB 에는 남음). 실패하면 던진다
  const deleteOne = useCallback(
    async (id: number) => {
      await deleteConversation(id)
      remove(id)
    },
    [remove],
  )
  // 서버가 돌려준 대화로 바꾼다 (목록에서 종료했을 때)
  const replaceOne = useCallback(
    (c: Conversation) => setData((prev) => prev.map((p) => (p.id === c.id ? { ...p, ...c } : p))),
    [setData],
  )
  // 대화방에 들어가면 그 줄의 숫자를 바로 지운다 (서버 읽음 처리는 대화방이 한다)
  const markSeen = useCallback(
    (id: number) => setData((prev) => prev.map((p) => (p.id === id ? { ...p, unread: 0 } : p))),
    [setData],
  )
  return { replaceOne, refresh, markSeen, remove, deleteOne, conversations: data, loading: !loaded && error === null, error, add }
}
