import { useSync } from './useSync'

// 열려 있는 대화를 최신으로 유지한다: {"type":"changed","conversation_id":N} 이 오면 바로, 연결이 없으면 2초마다.
export function useConversationSync(conversationId: number, refresh: () => void) {
  useSync(conversationId, refresh, (e) => e.type === 'changed' && e.conversationId === conversationId)
}
