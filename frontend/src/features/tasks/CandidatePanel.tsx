import type { Task } from '../../api/types'
import TaskItem from './TaskItem'

// 종료된 대화 안의 "할 일·일정 후보" 영역 (데모의 .candidate-box). 추가(status: added)하면 목록에서 빠지고
// 할 일·캘린더 탭에 나타난다.
export default function CandidatePanel({
  candidates,
  loading,
  error,
  onUpdated,
  onRemoved,
}: {
  candidates: Task[]
  loading: boolean
  error: string | null
  onUpdated: (task: Task) => void
  onRemoved: (id: number) => void
}) {
  return (
    <section className="candidate-box">
      <div className="eyebrow">SUGGESTED TO-DOS</div>
      <h3>할 일·일정 후보</h3>
      <p className="info">확인 후 [추가]를 눌러 할 일·캘린더에 등록하세요.</p>
      {loading && <p className="loading">불러오는 중</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      {!loading && !error && candidates.length === 0 && <p className="info">후보가 없어요</p>}
      <ul className="plain-list">
        {candidates.map((t) => (
          // 할 일과 일정은 서버에서 같은 테이블(tasks)이라 id 가 겹치지 않는다
          <TaskItem
            key={t.id}
            task={t}
            variant="candidate"
            onUpdated={(updated) => (updated.status === 'candidate' ? onUpdated(updated) : onRemoved(updated.id))}
            onRemoved={onRemoved}
          />
        ))}
      </ul>
    </section>
  )
}
