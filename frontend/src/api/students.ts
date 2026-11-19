import { request } from './client'
import type { Startable } from './types'

// 학생 · 학생 메모장 (담임만, 학생마다 메모장 하나). 서버 schemas/student.py
// parent_name = 이어진 학부모 (없으면 null — 대화를 시작할 수 없고, 초대 코드로 잇는다)
export type Student = { id: number; name: string; has_memo: boolean; parent_name: string | null }

// 내 반 학생 (이름 순)
export function listStudents(): Promise<Student[]> {
  return request<Student[]>('/students')
}

export type StudentMemo = { student_id: number; body: string; updated_at: string | null }

export function getMemo(studentId: number): Promise<StudentMemo> {
  return request<StudentMemo>(`/students/${studentId}/memo`)
}

// 통째로 저장한다. 빈 글이면 비운다.
export function saveMemo(studentId: number, body: string): Promise<StudentMemo> {
  return request<StudentMemo>(`/students/${studentId}/memo`, { method: 'PUT', json: { body } })
}

// 반 초대 코드 (담임만). 없으면 서버가 만든다
export function getInviteCode(): Promise<{ code: string }> {
  return request<{ code: string }>('/students/invite')
}

// 학부모: 초대 코드로 자녀 하나 더 잇기 (자녀가 여럿이거나 담임이 다를 때). 돌려받는 것 = 대화 시작 목록의 한 줄
export function addChild(inviteCode: string, studentName: string): Promise<Startable> {
  return request<Startable>('/children', { method: 'POST', json: { invite_code: inviteCode, student_name: studentName } })
}
