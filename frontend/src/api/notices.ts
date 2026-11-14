import { request } from './client'
import type { Notice } from './types'

// 교사: 자기 공지 전부(초안 포함). 학부모: 받은 공지(게시된 것만). 서버가 역할로 거른다.
export function listNotices(): Promise<Notice[]> {
  return request<Notice[]>('/notices')
}

export function createNotice(input: { title: string; body: string }): Promise<Notice> {
  return request<Notice>('/notices', { method: 'POST', json: input })
}

// 초안만 고칠 수 있다. 게시된 공지는 서버가 409 로 막는다 (detail 문장을 그대로 안내한다).
export function updateNotice(id: number, patch: { title?: string; body?: string }): Promise<Notice> {
  return request<Notice>(`/notices/${id}`, { method: 'PATCH', json: patch })
}

// 초안만 지울 수 있다 (게시된 공지는 409). 서버는 204(본문 없음)를 돌려준다.
export async function deleteNotice(id: number): Promise<void> {
  await request<null>(`/notices/${id}`, { method: 'DELETE' })
}

// 게시: 그 교사와 대화가 있는 학부모 모두에게 보이게 된다.
export function sendNotice(id: number): Promise<Notice> {
  return request<Notice>(`/notices/${id}/send`, { method: 'POST' })
}
