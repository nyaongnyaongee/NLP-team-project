import { request } from './client'
import type { Faq, FaqDraft } from './types'

// 자주 묻는 질문(Q&A). 교사: 자기가 등록한 것. 학부모: 내 아이 담임 · 대화가 있는 교사가 등록한 것 (공지와 같은 기준).
// 등록하면 바로 학부모에게 보인다 (쓰는 중 상태 없음).
export function listFaqs(): Promise<Faq[]> {
  return request<Faq[]>('/faqs')
}

export function createFaq(input: { question: string; answer: string }): Promise<Faq> {
  return request<Faq>('/faqs', { method: 'POST', json: input })
}

export function updateFaq(id: number, patch: { question?: string; answer?: string }): Promise<Faq> {
  return request<Faq>(`/faqs/${id}`, { method: 'PATCH', json: patch })
}

export async function deleteFaq(id: number): Promise<void> {
  await request<null>(`/faqs/${id}`, { method: 'DELETE' })
}

// Q&A 초안: 교사의 짧은 메모(+ 대화창이면 그 대화)를 Claude 가 질문 · 답변 꼴로. 저장하지 않는다. 오류: 502, 503
export function makeFaqDraft(memo: string, conversationId?: number): Promise<FaqDraft> {
  return request<FaqDraft>('/drafts/faq', {
    method: 'POST',
    json: conversationId != null ? { memo, conversation_id: conversationId } : { memo },
  })
}
