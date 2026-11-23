import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const today = new Intl.DateTimeFormat('ko-KR', { timeZone: 'Asia/Seoul', month: 'long', day: 'numeric', weekday: 'short' })

// 교사 「대화 목록」 맨 위: 날짜 + 인사 한 줄, 그 아래 숫자 띠 (새 메시지 · 미완료 할 일). 누르면 그 목록으로.
// 이름 · 학교는 위 머리에 이미 있어서 다시 쓰지 않는다. 진행 중 대화 수는 목록 위 탭에 있다.
export default function TeacherDashboard({
  unreadCount,
  todoCount,
  onOpenConversations,
}: {
  unreadCount: number // 안 읽은 메시지가 있는 대화 수
  todoCount: number | null // null = 아직 못 읽음
  onOpenConversations: () => void
}) {
  const navigate = useNavigate()
  const [date] = useState(() => today.format(new Date()))
  return (
    <div className="dashboard home-dash">
      <p className="home-date">{date}</p>
      <h2 className="home-greet">오늘도 반갑습니다, 선생님</h2>
      <div className="stat-strip">
        <button type="button" onClick={onOpenConversations} className={unreadCount > 0 ? 'hot' : ''}>
          <span>새 메시지</span>
          <strong>{unreadCount}</strong>
        </button>
        <button type="button" onClick={() => navigate('/teacher/todos')} className={todoCount ? 'hot' : ''}>
          <span>미완료 할 일</span>
          <strong>{todoCount ?? '–'}</strong>
        </button>
      </div>
    </div>
  )
}
