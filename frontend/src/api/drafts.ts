import { request } from './client'
import type { NoticeDraft, ReplyDraft } from './types'

// 답장 초안. Claude 를 기다리므로 몇 초 걸린다. 오류: 409(답장할 학부모 메시지 없음), 502(AI 실패), 503(AI 꺼짐)
// 모두 서버의 detail 문장이 오류 메시지가 된다 (client.ts).
export function makeReplyDraft(conversationId: number, memo?: string): Promise<ReplyDraft> {
  return request<ReplyDraft>(`/conversations/${conversationId}/draft`, { method: 'POST', json: memo ? { memo } : {} })
}

// 공지 초안. 대화창에서는 conversationId 를 주면 요점 없이도 그 대화를 보고 쓴다. 오류: 409(대화에 내용 없음), 502, 503
export function makeNoticeDraft(points: string, conversationId?: number): Promise<NoticeDraft> {
  return request<NoticeDraft>('/drafts/notice', {
    method: 'POST',
    json: conversationId != null ? { points, conversation_id: conversationId } : { points },
  })
}
