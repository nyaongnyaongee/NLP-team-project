import { useConversations } from '../chat/useConversations'
import ParentChat from './ParentChat'

// 학부모 "대화" 탭 (S2~S4 의 학부모 화면)
export default function ParentConversationTab() {
  const { conversations, loading, error } = useConversations()
  const first = conversations[0] // 내 대화 목록의 첫 대화를 자동 선택 (시드 대화, 치명 1)

  return (
    <div>
      {loading && <p className="loading">불러오는 중</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      {!loading && !error && !first && (
        <div className="empty">
          <div className="big">▤</div>아직 대화가 없어요
        </div>
      )}
      {first && <ParentChat conversation={first} />}
    </div>
  )
}
