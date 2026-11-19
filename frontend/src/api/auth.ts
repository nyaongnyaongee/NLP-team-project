import { request } from './client'
import type { LoginRes } from './types'

// 요청 본문 필드는 명세에 없어 서버 코드(schemas/message.py LoginIn)를 보고 login_id, password 로 정했다.
export function login(loginId: string, password: string): Promise<LoginRes> {
  return request<LoginRes>('/auth/login', {
    method: 'POST',
    json: { login_id: loginId, password },
    auth: false,
  })
}

// 가입 없이 들어오기 (시연): 담임의 반 초대 코드 + 자녀 이름 + 보호자 이름 → 학부모 계정이 바로 생긴다.
export function joinWithCode(inviteCode: string, studentName: string, parentName: string): Promise<LoginRes> {
  return request<LoginRes>('/auth/join', {
    method: 'POST',
    json: { invite_code: inviteCode, student_name: studentName, parent_name: parentName },
    auth: false,
  })
}
