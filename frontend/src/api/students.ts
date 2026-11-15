import { request } from './client'

// 학생 · 학생 메모장 (담임만, 학생마다 메모장 하나). 서버 schemas/student.py
export type Student = { id: number; name: string; has_memo: boolean }

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
