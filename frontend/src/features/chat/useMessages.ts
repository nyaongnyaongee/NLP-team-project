import { useCallback } from 'react'
import { listMessages } from '../../api/messages'
import type { Message } from '../../api/types'
import { useResource } from './useResource'

const NO_MESSAGES: Message[] = []

// 대화 하나의 메시지 목록. 서버 응답으로 목록 전체를 바꾸므로 같은 id 가 두 번 생기지 않는다.
export function useMessages(conversationId: number) {
  const load = useCallback(() => listMessages(conversationId), [conversationId])
  const { data, setData, loaded, error, refresh } = useResource(load, NO_MESSAGES)

  // 서버가 돌려준 메시지(내가 보낸 글, 다시 정제한 글)를 바로 반영한다. 같은 id 가 있으면 바꾸고 없으면 붙인다.
  const upsert = useCallback(
    (m: Message) => {
      setData((prev) => (prev.some((p) => p.id === m.id) ? prev.map((p) => (p.id === m.id ? m : p)) : [...prev, m]))
    },
    [setData],
  )

  return { messages: data, loading: !loaded && error === null, error, refresh, upsert }
}
