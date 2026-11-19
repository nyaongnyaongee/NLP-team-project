import { useState, type FormEvent } from 'react'
import { revealRef } from '../chat/useReveal'
import { fromDateInput, kstDateKey } from './formatDate'

export type ManualTaskInput = { title: string; due_at: string | null; shared: boolean }

// 교사가 직접 일정·할 일을 등록하는 폼 (캘린더 「＋ 일정 추가」, 할 일 「＋ 할 일 추가」 공용).
// 일정은 오늘 날짜로 시작하고 「학부모 캘린더에도 보이기」 체크가 있다. 할 일은 기한을 비워 둘 수 있다 (기한 없는 할 일은 목록 맨 아래).
export default function ManualTaskForm<T>({
  kind,
  onSubmit,
  onCancel,
  onAdded,
}: {
  kind: 'todo' | 'event'
  onSubmit: (input: ManualTaskInput) => Promise<T>
  onCancel: () => void
  onAdded: (created: T) => void
}) {
  const isEvent = kind === 'event'
  const word = isEvent ? '일정' : '할 일'
  const [title, setTitle] = useState('')
  const [date, setDate] = useState(() => (isEvent ? (kstDateKey(new Date()) ?? '') : ''))
  const [time, setTime] = useState('')
  const [shared, setShared] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (title.trim() === '') {
      setError('제목을 입력해 주세요')
      return
    }
    // 시각을 비우면 그날 00:00 (화면에는 「종일」). 날짜를 비우면 기한 없음
    const dueAt = date === '' ? null : time === '' ? fromDateInput(date) : `${date}T${time}:00+09:00`
    setBusy(true)
    setError(null)
    try {
      onAdded(await onSubmit({ title: title.trim(), due_at: dueAt, shared }))
    } catch (err) {
      setError(err instanceof Error ? err.message : '등록하지 못했습니다')
      setBusy(false)
    }
  }

  return (
    <form className="manual-form" onSubmit={(e) => void submit(e)} ref={revealRef}>
      <label className="editor-label" htmlFor={`${kind}-title`}>{word}</label>
      <input
        id={`${kind}-title`}
        value={title}
        maxLength={100}
        placeholder={isEvent ? '예: 가을 운동회' : '예: 가정통신문 인쇄'}
        onChange={(e) => setTitle(e.target.value)}
      />
      <div className="form-row">
        <div>
          <label className="editor-label" htmlFor={`${kind}-date`}>{isEvent ? '날짜' : '기한 (선택)'}</label>
          <input id={`${kind}-date`} type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </div>
        <div>
          <label className="editor-label" htmlFor={`${kind}-time`}>시각 (선택)</label>
          <input id={`${kind}-time`} type="time" value={time} onChange={(e) => setTime(e.target.value)} />
        </div>
      </div>
      {isEvent && (
        <label className="share-check">
          <input type="checkbox" checked={shared} onChange={(e) => setShared(e.target.checked)} />
          반 학부모 캘린더에도 보이기
        </label>
      )}
      {error && <p className="alert" role="alert">{error}</p>}
      <div className="form-actions">
        <button type="button" className="outline" onClick={onCancel} disabled={busy}>
          취소
        </button>
        <button type="submit" className="primary" disabled={busy}>
          등록
        </button>
      </div>
    </form>
  )
}
