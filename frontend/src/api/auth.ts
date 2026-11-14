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
