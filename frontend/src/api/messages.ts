import { request } from './client'
import type { Message } from './types'

export function listMessages(conversationId: number): Promise<Message[]> {
  return request<Message[]>(`/conversations/${conversationId}/messages`)
}

// 담임 교사만, 학부모가 보낸 메시지에만. 서버가 pending 으로 바꾸고 백그라운드에서 다시 정제한다 (202).
export function refineMessage(conversationId: number, messageId: number): Promise<Message> {
  return request<Message>(`/conversations/${conversationId}/messages/${messageId}/refine`, { method: 'POST' })
}

// 요청 본문 필드는 서버 코드(schemas/message.py MessageIn)를 보고 text 로 정했다.
export function sendMessage(conversationId: number, text: string): Promise<Message> {
  return request<Message>(`/conversations/${conversationId}/messages`, {
    method: 'POST',
    json: { text },
  })
}
