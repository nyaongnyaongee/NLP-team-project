import { request } from './client'
import type {
  ComplaintCaseDetail,
  ComplaintCaseSummary,
  ComplaintChannel,
  ComplaintChatMessage,
  ComplaintChatSummary,
} from './types'

export function listComplaints(): Promise<ComplaintCaseSummary[]> {
  return request<ComplaintCaseSummary[]>('/complaints')
}

export function submitComplaint(conversationIds: number[], reason: string): Promise<ComplaintCaseSummary> {
  return request<ComplaintCaseSummary>('/complaints', {
    method: 'POST',
    json: { conversation_ids: conversationIds, reason },
  })
}

// 담당자가 상세를 처음 열면 서버가 접수됨 → 진행 중으로 변경한다.
export function getComplaint(id: number): Promise<ComplaintCaseDetail> {
  return request<ComplaintCaseDetail>(`/complaints/${id}`)
}

export function completeComplaint(id: number): Promise<ComplaintCaseSummary> {
  return request<ComplaintCaseSummary>(`/complaints/${id}/complete`, { method: 'POST' })
}

export function retryComplaintReport(id: number): Promise<ComplaintCaseSummary> {
  return request<ComplaintCaseSummary>(`/complaints/${id}/report/retry`, { method: 'POST' })
}

export function listComplaintChats(channel: ComplaintChannel): Promise<ComplaintChatSummary[]> {
  return request<ComplaintChatSummary[]>(`/complaints/chats/${channel}`)
}

export function listComplaintChatMessages(caseId: number, channel: ComplaintChannel): Promise<ComplaintChatMessage[]> {
  return request<ComplaintChatMessage[]>(`/complaints/${caseId}/chats/${channel}/messages`)
}

export function markComplaintChatRead(caseId: number, channel: ComplaintChannel, messageId: number): Promise<void> {
  return request<void>(`/complaints/${caseId}/chats/${channel}/read`, {
    method: 'POST',
    json: { message_id: messageId },
  })
}

export function sendComplaintChatMessage(caseId: number, channel: ComplaintChannel, text: string): Promise<ComplaintChatMessage> {
  return request<ComplaintChatMessage>(`/complaints/${caseId}/chats/${channel}/messages`, {
    method: 'POST',
    json: { text },
  })
}
