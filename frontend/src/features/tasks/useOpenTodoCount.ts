import { useCallback } from 'react'
import { listTasks } from '../../api/tasks'
import { useSync } from '../../realtime/useSync'
import { useResource } from '../chat/useResource'

// 교사의 미완료 할 일 수 (추가했고 아직 완료 안 한 것). 대화가 바뀌면(추출이 끝나는 등) 다시 센다
export function useOpenTodoCount(): number | null {
  const load = useCallback(async () => (await listTasks('todo', { status: 'added' })).length, [])
  const { data, loaded, refresh } = useResource<number | null>(load, null)
  useSync('todo-count', refresh, (e) => e.type === 'changed')
  return loaded ? data : null
}
