import { useCallback, useState } from 'react'
import { closeConversation, deleteConversation } from '../../api/conversations'
import { sendMessage } from '../../api/messages'
import type { Conversation } from '../../api/types'
import { useConversationSync } from '../../realtime/useConversationSync'
import { teacherTitle } from '../chat/chatTitle'
import { formatTime } from '../chat/formatTime'
import MessageForm from '../chat/MessageForm'
import NewMessageButton from '../chat/NewMessageButton'
import { parentView } from '../chat/messageText'
import { useConversation } from '../chat/useConversation'
import { useChatScroll } from '../chat/useChatScroll'
import { useMarkRead } from '../chat/useMarkRead'
import { useMessages } from '../chat/useMessages'

// 학부모 대화방. 정제 상태(메시지 status)는 읽지도 표시하지도 않는다 (중대 5).
// 다만 내 글이 다듬어져 갔는지(refined)는 말풍선 아래에 「정제됨」으로 알리고, 누르면 선생님께 간 정제문을 펼친다.
// 표시하는 "대화 상태"는 대화(conversation)의 열림/닫힘이며 메시지의 정제 상태와 무관하다.
// 학부모도 「종료」로 대화를 닫을 수 있다 (할 일·일정 뽑기는 하지 않음 — 담임이 나중에 뽑는다).
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
  const [closing, setClosing] = useState(false) // 「종료」를 눌러 한 번 더 묻는 중 (아이폰 Safari 는 확인 창이 안 떠서 화면 안에서 묻는다)
  const [closeError, setCloseError] = useState<string | null>(null)
  const [openRefined, setOpenRefined] = useState<Set<number>>(() => new Set())
  const toggleRefined = (id: number) =>
    setOpenRefined((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  const { conversation, setConversation, refresh: refreshConversation } = useConversation(initial)
  const { messages, loading, error, upsert, refresh: refreshMessages } = useMessages(initial.id)
  useMarkRead(initial.id, messages)

  const refreshAll = useCallback(() => {
    void refreshMessages()
    void refreshConversation()
  }, [refreshMessages, refreshConversation])
  useConversationSync(initial.id, refreshAll)
  // 대화를 열면 맨 아래로, 새 글이 오면 아래를 보는 중일 때만 따라가고 위를 보는 중이면 「새 메시지」 버튼
  const { logRef, showNew, scrollToBottom } = useChatScroll(messages, (m) => m.sender_id !== conversation.teacher_id)

  // 종료된 대화에는 보낼 수 없다 (서버도 409). 입력창 대신 안내를 보인다.
  async function onSend(text: string) {
    try {
      upsert(await sendMessage(conversation.id, text))
    } finally {
      refreshAll() // 그사이 선생님이 종료했으면 종료 상태를 받는다. 조회 도중에 보낸 글이 오래된 응답에 지워지지 않게도 한다
    }
  }

  const onClose = async () => {
    setBusy(true)
    setCloseError(null)
    try {
      setConversation(await closeConversation(conversation.id, false))
      setClosing(false)
      refreshAll()
    } catch (e) {
      setCloseError(e instanceof Error ? e.message : '종료하지 못했습니다')
    } finally {
      setBusy(false)
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
      {/* 머리 한 줄: ‹ · 아바타 · 이름 ··· 대화 상태 */}
      <div className="chat-bar">
        <button type="button" className="bar-back" onClick={onBack} aria-label="대화 목록으로">
          ‹
        </button>
        <span className="avatar">{teacherTitle(conversation).slice(0, 1)}</span>
        <b className="bar-title">{teacherTitle(conversation)}</b>
        <span className="bar-actions">
          {conversation.status === 'closed' ? (
            <span className="tag">종료됨</span>
          ) : (
            <button type="button" className="head-action" onClick={() => setClosing((v) => !v)} disabled={busy}>
              종료
            </button>
          )}
        </span>
      </div>
      {conversation.status !== 'closed' && closing && (
        <div className="close-choice" role="group" aria-label="대화 종료">
          <p className="info">이 대화를 종료할까요? 종료하면 더 보낼 수 없고, 다른 문의는 「＋ 새 문의」로 보낼 수 있어요.</p>
          {closeError && <p className="alert" role="alert">{closeError}</p>}
          <button type="button" className="primary" onClick={() => void onClose()} disabled={busy}>
            대화 종료
          </button>
          <button type="button" className="back" onClick={() => setClosing(false)}>
            취소
          </button>
        </div>
      )}
      {loading && messages.length === 0 && <p className="loading">불러오는 중</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      {!loading && !error && messages.length === 0 && (
        <div className="empty">
          <div className="big">▤</div>아직 메시지가 없어요
        </div>
      )}
      <ul className="chat-log" ref={logRef}>
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
                <button
                  type="button"
                  className="refined-note"
                  title="거친 표현을 다듬어 선생님께 전달했어요"
                  aria-expanded={openRefined.has(m.id)}
                  onClick={() => toggleRefined(m.id)}
                >
                  정제됨 {openRefined.has(m.id) ? '▴' : '▾'}
                </button>
              )}
              {view.refined && openRefined.has(m.id) && (
                <div className="refined-text">
                  <div className="refined-text-label">선생님께는 이렇게 전달됐어요</div>
                  {view.refinedText ?? '정제문을 불러오지 못했어요'}
                </div>
              )}
            </li>
          )
        })}
      </ul>
      {conversation.status === 'closed' ? (
        <>
          <div className="closed-note">
            종료된 대화입니다. 다른 문의는 대화 목록의 「＋ 새 문의」로 보내 주세요.
          </div>
          {deleteError && <p className="alert" role="alert">{deleteError}</p>}
          <button type="button" className="delete-item" onClick={() => void onDelete()} disabled={busy}>
            대화 삭제
          </button>
        </>
      ) : (
        <div className="chat-compose">
          <NewMessageButton visible={showNew} onClick={() => scrollToBottom()} />
          <MessageForm id="parent-message" label="선생님께 메시지 쓰기" onSend={onSend} />
        </div>
      )}
    </section>
  )
}
