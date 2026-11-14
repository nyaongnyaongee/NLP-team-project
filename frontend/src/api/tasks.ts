import { request } from './client'
import type { Task } from './types'

// 할 일(todo)과 일정(event)은 서버에서 모양이 같고 경로만 다르다 (/todos, /events).
const PATH: Record<Task['kind'], string> = { todo: '/todos', event: '/events' }

export type TaskFilter = { status?: Task['status']; conversationId?: number }

// 보낸 것만 바뀐다. due_at 에 null 을 보내면 날짜가 지워진다 (서버 schemas/todo.py TaskPatch).
export type TaskPatch = { title?: string; due_at?: string | null; status?: Task['status'] }

export function listTasks(kind: Task['kind'], filter: TaskFilter = {}): Promise<Task[]> {
  const query = new URLSearchParams()
  if (filter.status) query.set('status', filter.status)
  if (filter.conversationId !== undefined) query.set('conversation_id', String(filter.conversationId))
  const qs = query.toString()
  return request<Task[]>(`${PATH[kind]}${qs ? `?${qs}` : ''}`)
}

export function updateTask(kind: Task['kind'], id: number, patch: TaskPatch): Promise<Task> {
  return request<Task>(`${PATH[kind]}/${id}`, { method: 'PATCH', json: patch })
}

// 서버는 204(본문 없음)를 돌려준다.
export async function deleteTask(kind: Task['kind'], id: number): Promise<void> {
  await request<null>(`${PATH[kind]}/${id}`, { method: 'DELETE' })
}
