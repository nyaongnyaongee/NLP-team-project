import { listParentEvents } from '../../api/tasks'
import type { ParentEvent } from '../../api/types'
import { useSync } from '../../realtime/useSync'
import { useResource } from '../chat/useResource'
import { formatTimeOfDay, NO_DUE } from '../tasks/formatDate'
import MonthCalendar from '../tasks/MonthCalendar'

const NONE: ParentEvent[] = []

// 학부모 "캘린더" 탭: 선생님이 공유한 일정 (반 전체 일정 + 내 대화에서 정한 일정). 읽기만 한다.
// 선생님이 일정을 등록 · 수정 · 삭제하면 서버가 {"type":"events"} 를 보내 다시 읽는다.
export default function ParentCalendar() {
  const { data: events, loaded, error, refresh } = useResource(listParentEvents, NONE)
  useSync('parent-events', refresh, (e) => e.type === 'events')
  const loading = !loaded && error === null

  return (
    <section>
      <div className="eyebrow">CALENDAR</div>
      <div className="tool-heading">
        <h2>
          학교 일정,
          <br />
          한눈에 확인하세요.
        </h2>
      </div>
      {loading && <p className="loading">불러오는 중</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      <MonthCalendar
        items={events}
        loading={loading || error !== null}
        renderItem={(e) => (
          <li key={e.id} className="agenda">
            <span className="event-time">{e.due_at ? formatTimeOfDay(e.due_at) : NO_DUE}</span>
            <div>
              <b>{e.title}</b>
              <small>
                {e.teacher_name} 선생님 · {e.student_name ?? '반 전체'}
                {e.status === 'done' && ' · 끝남'}
              </small>
            </div>
          </li>
        )}
      />
    </section>
  )
}
