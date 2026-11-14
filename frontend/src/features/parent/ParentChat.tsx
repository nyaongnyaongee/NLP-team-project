import { useCallback } from 'react'
import { sendMessage } from '../../api/messages'
import type { Conversation } from '../../api/types'
import { useConversationSync } from '../../realtime/useConversationSync'
import { formatTime } from '../chat/formatTime'
import MessageForm from '../chat/MessageForm'
import { parentView } from '../chat/messageText'
import { useConversation } from '../chat/useConversation'
import { useMessages } from '../chat/useMessages'

// 학부모 대화방. 정제문과 정제 상태(메시지 status)는 읽지도 표시하지도 않는다 (중대 5).
// 표시하는 "대화 상태"는 대화(conversation)의 열림/닫힘이며 메시지의 정제 상태와 무관하다.
export default function ParentChat({ conversation: initial, onBack }: { conversation: Conversation; onBack: () => void }) {
  const { conversation, refresh: refreshConversation } = useConversation(initial)
  const { messages, loading, error, upsert, refresh: refreshMessages } = useMessages(initial.id)

  const refreshAll = useCallback(() => {
    void refreshMessages()
    void refreshConversation()
  }, [refreshMessages, refreshConversation])
  useConversationSync(initial.id, refreshAll)

  // 종료된 대화에도 입력창을 유지한다: 보내면 서버가 대화를 다시 연다.
  async function onSend(text: string) {
    const sent = await sendMessage(conversation.id, text)
    upsert(sent)
    refreshAll() // 다시 열린 대화 상태를 받고, 조회 도중에 보낸 경우 오래된 응답이 방금 보낸 글을 지우지 않게 한다
  }

  return (
    <section>
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
            </li>
          )
        })}
      </ul>
      <MessageForm id="parent-message" label="선생님께 메시지" onSend={onSend} />
    </section>
  )
}
