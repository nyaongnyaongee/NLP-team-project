import type { Conversation } from '../../api/types'

// 학부모가 보는 대화 상대 = 담임 (「김민지 선생님」). 예전 서버라 이름이 없으면 학생 이름으로
export const teacherTitle = (c: Conversation) => (c.teacher_name ? `${c.teacher_name} 선생님` : c.student_name)

// 교사가 보는 대화 상대 = 학부모 이름 + 누구 부모인지 (「박서연 (박지민 부모)」). 이름이 없으면 「박지민 부모」
export const parentTitle = (c: Conversation) =>
  c.parent_name ? `${c.parent_name} (${c.student_name} 부모)` : `${c.student_name} 부모`

// 교사 화면에서 이름을 두 칸으로 나눠 그릴 때 (굵은 이름 + 작은 회색 「박지민 부모」 — 길어도 밀리지 않게)
export function parentLabel(c: { parent_name?: string | null; student_name: string }): { name: string; sub: string | null } {
  return c.parent_name ? { name: c.parent_name, sub: `${c.student_name} 부모` } : { name: `${c.student_name} 부모`, sub: null }
}
