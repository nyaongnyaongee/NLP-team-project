import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { SCHOOL_NAME } from '../../components/AppShell'

// 교사 「대화 목록」 맨 위: 인사 + 숫자 카드 두 개 (진행 중인 대화 · 미완료 할 일). 숫자를 누르면 그 목록으로
export default function TeacherDashboard({
  openCount,
  todoCount,
  onOpenConversations,
}: {
  openCount: number
  todoCount: number | null // null = 아직 못 읽음
  onOpenConversations: () => void
}) {
  const { session } = useAuth()
  const navigate = useNavigate()
  const name = session?.name ?? ''
  return (
    <div className="dashboard">
      <div className="eyebrow">TEACHER</div>
      <div className="greeting">
        <span className="avatar big">{name.slice(0, 1)}</span>
        <h2>
          {name} 선생님,
          <br />
          오늘도 반갑습니다.
        </h2>
      </div>
      <p className="sub">{SCHOOL_NAME} · 담임</p>
      <div className="stat-cards">
        <button type="button" className="stat-card" onClick={onOpenConversations}>
          <span>진행 중인 대화</span>
          <strong>{openCount}</strong>
        </button>
        <button type="button" className="stat-card" onClick={() => navigate('/teacher/todos')}>
          <span>미완료 할 일</span>
          <strong>{todoCount ?? '–'}</strong>
        </button>
      </div>
    </div>
  )
}
