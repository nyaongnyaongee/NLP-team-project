import { useState, type FormEvent } from 'react'
import { createEvent } from '../../api/tasks'
import { fromDateInput, kstDateKey } from './formatDate'
import MonthCalendar from './MonthCalendar'
import TaskItem from './TaskItem'
import { useTaskList } from './useTaskList'

// 교사 "캘린더" 탭: 월 달력, 날짜를 선택하면 그날의 일정. 날짜가 없는 일정은 아래에 따로 보인다.
// 「＋ 일정 추가」로 반 전체 일정을 직접 등록한다. 「학부모와 공유」인 일정은 학부모 캘린더에도 보인다.
export default function CalendarTab() {
  const { tasks, loading, error, replace, remove, add } = useTaskList('event')
  const [adding, setAdding] = useState(false)

  return (
    <section>
      <div className="eyebrow">MY CALENDAR</div>
      <div className="tool-heading">
        <h2>
          선생님의 약속,
          <br />
          한눈에 확인하세요.
        </h2>
        {!adding && (
          <button type="button" className="manual-add" onClick={() => setAdding(true)}>
            ＋ 일정 추가
          </button>
        )}
      </div>
      {adding && (
        <AddEventForm
          onCancel={() => setAdding(false)}
          onAdded={(t) => {
            add(t)
            setAdding(false)
          }}
        />
      )}
      {loading && <p className="loading">불러오는 중</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      <MonthCalendar
        items={tasks}
        loading={loading || error !== null}
        renderItem={(t) => <TaskItem key={t.id} task={t} variant="event" onUpdated={replace} onRemoved={remove} />}
      />
    </section>
  )
}

function AddEventForm({
  onCancel,
  onAdded,
}: {
  onCancel: () => void
  onAdded: (t: Awaited<ReturnType<typeof createEvent>>) => void
}) {
  const [title, setTitle] = useState('')
  const [date, setDate] = useState(() => kstDateKey(new Date()) ?? '')
  const [time, setTime] = useState('')
  const [shared, setShared] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (title.trim() === '') {
      setError('제목을 입력해 주세요')
      return
    }
    // 시각을 비우면 그날 00:00 (화면에는 「종일」)
    const dueAt = date === '' ? null : time === '' ? fromDateInput(date) : `${date}T${time}:00+09:00`
    setBusy(true)
    setError(null)
    try {
      onAdded(await createEvent({ title: title.trim(), due_at: dueAt, shared }))
    } catch (err) {
      setError(err instanceof Error ? err.message : '등록하지 못했습니다')
      setBusy(false)
    }
  }

  return (
    <form className="manual-form" onSubmit={(e) => void onSubmit(e)}>
      <label className="editor-label" htmlFor="event-title">일정</label>
      <input id="event-title" value={title} maxLength={100} placeholder="예: 가을 운동회" onChange={(e) => setTitle(e.target.value)} />
      <div className="form-row">
        <div>
          <label className="editor-label" htmlFor="event-date">날짜</label>
          <input id="event-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </div>
        <div>
          <label className="editor-label" htmlFor="event-time">시각 (선택)</label>
          <input id="event-time" type="time" value={time} onChange={(e) => setTime(e.target.value)} />
        </div>
      </div>
      <label className="share-check">
        <input type="checkbox" checked={shared} onChange={(e) => setShared(e.target.checked)} />
        반 학부모 캘린더에도 보이기
      </label>
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
