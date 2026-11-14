import { useCallback } from 'react'
import { listTasks } from '../../api/tasks'
import type { Task } from '../../api/types'
import { useResource } from '../chat/useResource'

const NO_TASKS: Task[] = []

// 한 종류(할 일 또는 일정)의 "추가된 것과 완료한 것" 목록. 후보(candidate)는 대화 안의 후보 영역에서 다룬다.
export function useTaskList(kind: Task['kind']) {
  const load = useCallback(async () => (await listTasks(kind)).filter((t) => t.status !== 'candidate'), [kind])
  const { data, setData, loaded, error } = useResource(load, NO_TASKS)

  const replace = useCallback((t: Task) => setData((prev) => prev.map((p) => (p.id === t.id ? t : p))), [setData])
  const remove = useCallback((id: number) => setData((prev) => prev.filter((p) => p.id !== id)), [setData])

  return { tasks: data, loading: !loaded && error === null, error, replace, remove }
}
