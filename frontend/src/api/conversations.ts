import { request } from './client'
import type { Conversation, Startable } from './types'

export function listConversations(): Promise<Conversation[]> {
  return request<Conversation[]>('/conversations')
}

export function listStartable(): Promise<Startable[]> {
  return request<Startable[]>('/conversations/startable')
}

// 교사·학부모 둘 다. 문의마다 새 대화방을 만든다(201). 상대에게 알림이 간다.
export function startConversation(studentId: number): Promise<Conversation> {
  return request<Conversation>('/conversations/start', { method: 'POST', json: { student_id: studentId } })
}

export function getConversation(id: number): Promise<Conversation> {
  return request<Conversation>(`/conversations/${id}`)
}

// 담임 교사만. extract 가 true 면 서버가 백그라운드에서 할 일·일정 후보 추출을 시작한다 (202). false 면 닫기만.
export function closeConversation(id: number, extract: boolean): Promise<Conversation> {
  return request<Conversation>(`/conversations/${id}/close`, { method: 'POST', json: { extract } })
}

// 담임 · 학부모 각자, 종료된 대화만 (아니면 409). 내 목록에서만 사라지고 DB 에는 남는다 (204).
export async function deleteConversation(id: number): Promise<void> {
  await request<null>(`/conversations/${id}`, { method: 'DELETE' })
}

// 지금까지 온 메시지를 읽음으로 (204). 대화방을 보고 있을 때 부른다.
export async function markRead(id: number): Promise<void> {
  await request<null>(`/conversations/${id}/read`, { method: 'POST' })
}

// 닫힌 대화에서만 (아니면 409).
export function extractAgain(id: number): Promise<Conversation> {
  return request<Conversation>(`/conversations/${id}/extract`, { method: 'POST' })
}
