import StartConversation from '../chat/StartConversation'
import { useConversations } from '../chat/useConversations'
import ParentChat from './ParentChat'

// 학부모 "대화" 탭 (S2~S4 의 학부모 화면). 대화가 없으면 내 아이의 담임과 대화를 시작한다.
export default function ParentConversationTab() {
  const { conversations, loading, error, add } = useConversations()
  // 열린 대화를 먼저, 없으면 가장 최근 대화 (닫힌 대화에 보내면 서버가 다시 연다)
  const first = conversations.find((c) => c.status === 'open') ?? conversations[conversations.length - 1]

  return (
    <div>
      {loading && <p className="loading">불러오는 중</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      {!loading && !error && !first && <StartConversation role="parent" onStarted={add} />}
      {first && <ParentChat key={first.id} conversation={first} />}
    </div>
  )
}
