import type { Role } from '../api/types'

// 명세 8장: 토큰은 sessionStorage (탭을 닫으면 풀린다). 새로고침 후 복구를 위해 이름·역할도 함께 둔다.
// 서버에 "내 정보" 조회 API 가 없어서 이름·역할을 다시 받을 방법이 없다.
// 원문(raw_text)은 여기에 저장하지 않는다 (4.4-8).

export type Session = { token: string; name: string; role: Role }

const KEY = 'ieum.session'
const ROLES: Role[] = ['parent', 'teacher', 'complaint_team']

export function loadSession(): Session | null {
  try {
    const raw = sessionStorage.getItem(KEY)
    if (!raw) return null
    const v = JSON.parse(raw) as Partial<Session>
    if (
      typeof v.token === 'string' &&
      v.token !== '' &&
      typeof v.name === 'string' &&
      ROLES.includes(v.role as Role)
    ) {
      return { token: v.token, name: v.name, role: v.role as Role }
    }
  } catch {
    // 저장소를 못 읽거나 값이 망가졌으면 로그인하지 않은 것으로 본다.
  }
  return null
}

export function saveSession(s: Session): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(s))
  } catch {
    // 저장에 실패해도 이번 화면에서는 로그인 상태를 유지한다 (새로고침하면 풀림).
  }
}

export function clearSession(): void {
  try {
    sessionStorage.removeItem(KEY)
  } catch {
    // 무시
  }
}
