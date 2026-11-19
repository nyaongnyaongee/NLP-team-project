import { useState } from 'react'
import { createEvent } from '../../api/tasks'
import ManualTaskForm from './ManualTaskForm'
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
        <ManualTaskForm
          kind="event"
          onSubmit={createEvent}
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
