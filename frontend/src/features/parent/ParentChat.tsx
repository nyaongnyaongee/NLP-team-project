import { useCallback, useState } from 'react'
import { deleteConversation } from '../../api/conversations'
import { sendMessage } from '../../api/messages'
import type { Conversation } from '../../api/types'
import { useConversationSync } from '../../realtime/useConversationSync'
import { formatTime } from '../chat/formatTime'
import MessageForm from '../chat/MessageForm'
import { parentView } from '../chat/messageText'
import { useConversation } from '../chat/useConversation'
import { useMarkRead } from '../chat/useMarkRead'
import { useMessages } from '../chat/useMessages'

// 학부모 대화방. 정제문과 정제 상태(메시지 status)는 읽지도 표시하지도 않는다 (중대 5).
// 다만 내 글이 다듬어져 갔는지(refined)는 말풍선 아래에 작게 알린다.
// 표시하는 "대화 상태"는 대화(conversation)의 열림/닫힘이며 메시지의 정제 상태와 무관하다.
// onDeleted: 종료된 대화를 내 목록에서 지운 뒤 (목록에서 빼고 돌아간다)
export default function ParentChat({
  conversation: initial,
  onBack,
  onDeleted,
}: {
  conversation: Conversation
  onBack: () => void
  onDeleted: (id: number) => void
}) {
  const [busy, setBusy] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const { conversation, refresh: refreshConversation } = useConversation(initial)
  const { messages, loading, error, upsert, refresh: refreshMessages } = useMessages(initial.id)
  useMarkRead(initial.id, messages)

  const refreshAll = useCallback(() => {
    void refreshMessages()
    void refreshConversation()
  }, [refreshMessages, refreshConversation])
  useConversationSync(initial.id, refreshAll)

  // 종료된 대화에는 보낼 수 없다 (서버도 409). 입력창 대신 안내를 보인다.
  async function onSend(text: string) {
    try {
      upsert(await sendMessage(conversation.id, text))
    } finally {
      refreshAll() // 그사이 선생님이 종료했으면 종료 상태를 받는다. 조회 도중에 보낸 글이 오래된 응답에 지워지지 않게도 한다
    }
  }

  const onDelete = async () => {
    if (!window.confirm('이 대화를 목록에서 삭제할까요?')) return
    setBusy(true)
    setDeleteError(null)
    try {
      await deleteConversation(conversation.id)
      onDeleted(conversation.id)
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : '삭제하지 못했습니다')
      setBusy(false)
    }
  }

  return (
    <section className="chat-screen">
      <div className="chat-head">
        <button type="button" className="back" onClick={onBack}>
          ‹ 대화 목록
        </button>
        <span className="tag">{conversation.status === 'closed' ? '종료된 대화' : '대화 중'}</span>
      </div>
      <div className="chat-person">
        <span className="avatar">{conversation.student_name.slice(0, 1)}</span>
        <div>
          <b>{conversation.student_name}</b>
        </div>
      </div>
      {loading && messages.length === 0 && <p className="loading">불러오는 중</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      {!loading && !error && messages.length === 0 && (
        <div className="empty">
          <div className="big">▤</div>아직 메시지가 없어요
        </div>
      )}
      <ul className="chat-log">
        {messages.map((m) => {
          // 교사 글이 아니면 학부모(나)의 글이다 (중대 4)
          const mine = m.sender_id !== conversation.teacher_id
          const view = parentView(m)
          return (
            <li key={m.id} className={`chat-message ${mine ? 'mine' : ''}`}>
              <div className="chat-name">
                {mine ? '나' : '선생님'} <span>{formatTime(m.created_at)}</span>
              </div>
              <div className="chat-bubble">{view.text}</div>
              {view.refined && (
                <div className="refined-note" title="거친 표현을 다듬어 선생님께 전달했어요">
                  정제됨
                </div>
              )}
            </li>
          )
        })}
      </ul>
      {conversation.status === 'closed' ? (
        <>
          <div className="closed-note">
            선생님이 종료한 대화입니다. 다른 문의는 대화 목록의 「＋ 새 문의」로 보내 주세요.
          </div>
          {deleteError && <p className="alert" role="alert">{deleteError}</p>}
          <button type="button" className="delete-item" onClick={() => void onDelete()} disabled={busy}>
            대화 삭제
          </button>
        </>
      ) : (
        <div className="chat-compose">
          <MessageForm id="parent-message" label="선생님께 메시지 쓰기" onSend={onSend} />
        </div>
      )}
    </section>
  )
}
