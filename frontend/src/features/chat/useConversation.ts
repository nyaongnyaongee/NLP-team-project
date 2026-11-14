import { useCallback } from 'react'
import { getConversation } from '../../api/conversations'
import type { Conversation } from '../../api/types'
import { useResource } from './useResource'

// 열려 있는 대화 하나의 최신 상태(열림/닫힘, 교사에게는 추출 상태). 목록에서 받은 값으로 시작한다.
export function useConversation(initial: Conversation) {
  const id = initial.id
  const load = useCallback(() => getConversation(id), [id])
  const { data, setData, error, refresh } = useResource(load, initial)
  return { conversation: data, setConversation: setData, error, refresh }
}
