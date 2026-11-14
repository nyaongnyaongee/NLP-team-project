import { useState } from 'react'
import ConversationList from '../chat/ConversationList'
import StartConversation from '../chat/StartConversation'
import { useConversations } from '../chat/useConversations'
import ParentChat from './ParentChat'

// 학부모 "대화" 탭: 대화 목록 → 대화방 (‹ 대화 목록 으로 돌아옴). 문의마다 「＋ 새 문의」로 새 대화방을 연다.
export default function ParentConversationTab() {
  const { conversations, loading, error, add } = useConversations()
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [starting, setStarting] = useState(false)
  const selected = conversations.find((c) => c.id === selectedId) ?? null

  if (selected) {
    return <ParentChat key={selected.id} conversation={selected} onBack={() => setSelectedId(null)} />
  }

  const empty = !loading && !error && conversations.length === 0
  return (
    <section>
      <div className="eyebrow">CONVERSATIONS</div>
      <div className="notice-heading">
        <h2>선생님과의 대화</h2>
        {!starting && !empty && (
          <button type="button" className="notice-create" onClick={() => setStarting(true)}>
            ＋ 새 문의
          </button>
        )}
      </div>
      {loading && <p className="loading">불러오는 중</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      {(starting || empty) && (
        <StartConversation
          role="parent"
          onCancel={empty ? undefined : () => setStarting(false)}
          onStarted={(c) => {
            add(c)
            setStarting(false)
            setSelectedId(c.id)
          }}
        />
      )}
      {empty && <p className="sub">문의할 내용마다 새 대화를 열 수 있어요</p>}
      <ConversationList conversations={conversations} onSelect={setSelectedId} />
    </section>
  )
}
