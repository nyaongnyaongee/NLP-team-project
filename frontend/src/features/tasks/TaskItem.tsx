import { useRef, useState, type FormEvent } from 'react'
import { ApiError } from '../../api/client'
import { deleteTask, updateTask, type TaskPatch } from '../../api/tasks'
import type { Task } from '../../api/types'
import { formatDate, formatTimeOfDay, fromDateInput, NO_DUE, toDateInput } from './formatDate'

// candidate: 종료된 대화의 후보, todo: 할 일 탭, event: 캘린더 탭 (데모의 .candidate, .todo, .agenda 모양)
export type TaskVariant = 'candidate' | 'todo' | 'event'

const MAX_TITLE = 100 // 서버 TaskPatch.title 최대 길이

// 후보, 할 일, 일정이 함께 쓰는 한 줄. 어떤 버튼을 보일지는 variant 로 정한다.
export default function TaskItem({
  task,
  variant,
  onUpdated,
  onRemoved,
}: {
  task: Task
  variant: TaskVariant
  onUpdated: (task: Task) => void
  onRemoved: (id: number) => void
}) {
  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState(task.title)
  const [date, setDate] = useState(toDateInput(task.due_at))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const busyRef = useRef(false) // 연타로 같은 요청이 두 번 나가는 것을 막는다

  async function run(action: () => Promise<void>) {
    if (busyRef.current) return
    busyRef.current = true
    setBusy(true)
    setError(null)
    try {
      await action()
    } catch (e) {
      // 다른 곳에서 이미 지워졌다면(404) 목록에서도 뺀다 (명세 3.1)
      if (e instanceof ApiError && e.status === 404) onRemoved(task.id)
      else setError(e instanceof Error ? e.message : '요청에 실패했습니다')
    } finally {
      busyRef.current = false
      setBusy(false)
    }
  }

  const patch = (body: TaskPatch, after?: () => void) =>
    run(async () => {
      onUpdated(await updateTask(task.kind, task.id, body))
      after?.()
    })

  const onDelete = () => {
    if (!window.confirm(`"${task.title}" 항목을 삭제할까요?`)) return
    void run(async () => {
      await deleteTask(task.kind, task.id)
      onRemoved(task.id)
    })
  }

  function startEdit() {
    setTitle(task.title)
    setDate(toDateInput(task.due_at))
    setError(null)
    setEditing(true)
  }

  function onSave(e: FormEvent) {
    e.preventDefault()
    const nextTitle = title.trim()
    if (nextTitle === '') {
      setError('제목을 입력해 주세요')
      return
    }
    const body: TaskPatch = {}
    if (nextTitle !== task.title) body.title = nextTitle
    // 날짜를 바꾼 경우에만 보낸다: 그대로 두면 서버에 있는 시각(00:00 이 아닌 경우)을 지우지 않는다.
    if (date !== toDateInput(task.due_at)) body.due_at = fromDateInput(date)
    if (Object.keys(body).length === 0) {
      setEditing(false)
      return
    }
    void patch(body, () => setEditing(false))
  }

  const kindLabel = task.kind === 'todo' ? '할 일' : '일정'
  const hasDue = task.due_at !== null

  if (editing) {
    return (
      <li>
        <form className="manual-form" onSubmit={onSave}>
          <span className="tag">{kindLabel}</span>
          <label className="editor-label" htmlFor={`task-title-${task.id}`}>제목</label>
          <input
            id={`task-title-${task.id}`}
            value={title}
            maxLength={MAX_TITLE}
            onChange={(e) => setTitle(e.target.value)}
          />
          <label className="editor-label" htmlFor={`task-date-${task.id}`}>날짜</label>
          <input id={`task-date-${task.id}`} type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          {error && <p className="alert" role="alert">{error}</p>}
          <div className="form-actions">
            <button
              type="button"
              className="outline"
              onClick={() => {
                setError(null)
                setEditing(false)
              }}
              disabled={busy}
            >
              취소
            </button>
            <button type="submit" className="primary" disabled={busy}>
              저장
            </button>
          </div>
        </form>
      </li>
    )
  }

  const edit = (
    <button type="button" className="item-edit" onClick={startEdit} disabled={busy}>
      수정
    </button>
  )
  const del = (
    <button type="button" className="item-edit danger" onClick={onDelete} disabled={busy}>
      삭제
    </button>
  )
  const errorLine = error && <p className="alert" role="alert">{error}</p>

  if (variant === 'todo') {
    return (
      <li className={`todo ${task.status === 'done' ? 'done' : ''}`}>
        <label className="todo-check">
          <input
            type="checkbox"
            aria-label={`${task.title} 완료`}
            checked={task.status === 'done'}
            disabled={busy}
            onChange={(e) => void patch({ status: e.target.checked ? 'done' : 'added' })}
          />
          <span className="todo-body">
            <b>{task.title}</b>
            <small>
              {task.student_name} · {task.status === 'done' ? '완료' : '미완료'}
            </small>
            <span className="due">
              {formatDate(task.due_at)}
              {task.due_text && ` (${task.due_text})`}
            </span>
          </span>
        </label>
        <span className="task-actions">
          {edit}
          {del}
        </span>
        {errorLine}
      </li>
    )
  }

  if (variant === 'event') {
    return (
      <li className="agenda">
        <span className="event-time">{hasDue ? formatTimeOfDay(task.due_at) : NO_DUE}</span>
        <div>
          <b>{task.title}</b>
          <small>{task.student_name}</small>
          {errorLine}
        </div>
        <span className="task-actions">
          {edit}
          {del}
        </span>
      </li>
    )
  }

  // candidate
  return (
    <li className="candidate">
      <div>
        <span className="tag">{kindLabel}</span>
        <b>{task.title}</b>
        <span className="due">
          {hasDue ? `기한 · ${formatDate(task.due_at)}` : NO_DUE}
          {task.due_text && ` (${task.due_text})`}
        </span>
        {errorLine}
      </div>
      <span className="task-actions">
        <button type="button" className="add-task" onClick={() => void patch({ status: 'added' })} disabled={busy}>
          추가
        </button>
        {edit}
        {del}
      </span>
    </li>
  )
}
