import { request } from './client'
import type { Conversation, Startable } from './types'

export function listConversations(): Promise<Conversation[]> {
  return request<Conversation[]>('/conversations')
}

export function listStartable(): Promise<Startable[]> {
  return request<Startable[]>('/conversations/startable')
}

// 교사·학부모 둘 다. 열린 대화가 있으면 그 대화(200), 없으면 새로 만든다(201). 상대에게 알림이 간다.
export function startConversation(studentId: number): Promise<Conversation> {
  return request<Conversation>('/conversations/start', { method: 'POST', json: { student_id: studentId } })
}

export function getConversation(id: number): Promise<Conversation> {
  return request<Conversation>(`/conversations/${id}`)
}

// 담임 교사만. 서버가 백그라운드에서 할 일·일정 후보 추출을 시작한다 (202).
export function closeConversation(id: number): Promise<Conversation> {
  return request<Conversation>(`/conversations/${id}/close`, { method: 'POST' })
}

// 닫힌 대화에서만 (아니면 409).
export function extractAgain(id: number): Promise<Conversation> {
  return request<Conversation>(`/conversations/${id}/extract`, { method: 'POST' })
}
