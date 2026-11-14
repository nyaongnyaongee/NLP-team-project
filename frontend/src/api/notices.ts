import { request } from './client'
import type { Notice } from './types'

// 교사: 자기 공지 전부(초안 포함). 학부모: 받은 공지(게시된 것만). 서버가 역할로 거른다.
export function listNotices(): Promise<Notice[]> {
  return request<Notice[]>('/notices')
}

export function createNotice(input: { title: string; body: string }): Promise<Notice> {
  return request<Notice>('/notices', { method: 'POST', json: input })
}

// 초안도 게시된 공지도 고칠 수 있다. 게시된 공지를 고치면 학부모에게 알림이 가고 updated_at > sent_at 이 된다(수정됨).
export function updateNotice(id: number, patch: { title?: string; body?: string }): Promise<Notice> {
  return request<Notice>(`/notices/${id}`, { method: 'PATCH', json: patch })
}

// 게시된 공지도 지울 수 있다 (학부모 화면에서도 사라진다). 서버는 204(본문 없음)를 돌려준다.
export async function deleteNotice(id: number): Promise<void> {
  await request<null>(`/notices/${id}`, { method: 'DELETE' })
}

// 게시: 반 학생의 학부모 모두에게 보이게 된다 (+ 대화가 있는 학부모). 다시 게시하면 409.
export function sendNotice(id: number): Promise<Notice> {
  return request<Notice>(`/notices/${id}/send`, { method: 'POST' })
}
