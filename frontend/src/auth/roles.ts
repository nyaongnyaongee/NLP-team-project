import type { Role } from '../api/types'

// 명세 8장 주소 구조: 역할별 시작 경로
export const HOME_PATH: Record<Role, string> = {
  parent: '/parent',
  teacher: '/teacher',
  complaint_team: '/team',
}

export const ROLE_LABEL: Record<Role, string> = {
  parent: '학부모',
  teacher: '교사',
  complaint_team: '민원이관팀',
}
