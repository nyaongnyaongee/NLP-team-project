import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { listComplaintChatMessages, markComplaintChatRead, sendComplaintChatMessage } from '../../api/complaints'
import type { ComplaintChannel, ComplaintChatMessage, ComplaintStatus } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { useSync } from '../../realtime/useSync'
import { formatTime } from '../chat/formatTime'
import { useResource } from '../chat/useResource'

const EMPTY: ComplaintChatMessage[] = []

// 민원담당자와 학부모/교사가 각각 나누는 별도 채팅. 신청 사유·보고서·기존 대화는 이 API로 읽지 않는다.
export default function ComplaintChatThread({
  caseId,
  channel,
  counterpartName,
  status,
  onBack,
  onRead,
}: {
  caseId: number
  channel: ComplaintChannel
  counterpartName: string
  status: Exclude<ComplaintStatus, 'received'>
  onBack: () => void
  onRead?: () => void
}) {
  const { session } = useAuth()
  const load = useCallback(() => listComplaintChatMessages(caseId, channel), [caseId, channel])
  const { data: messages, loaded, error, refresh } = useResource(load, EMPTY)
  useSync(`complaint-chat-${caseId}-${channel}`, refresh, (event) =>
    event.type === 'complaints' && (event.caseId === null || event.caseId === caseId),
  )
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [sendError, setSendError] = useState<string | null>(null)
  const completed = status === 'completed'
  const visibleMessages = messages.filter((message) => message.case_id === caseId && message.channel === channel)
  const lastMessageId = visibleMessages.length ? visibleMessages[visibleMessages.length - 1].id : null
  const onReadRef = useRef(onRead)
  useEffect(() => { onReadRef.current = onRead }, [onRead])
  useEffect(() => {
    if (lastMessageId === null) return
    const markVisible = () => {
      if (!document.hidden) {
        void markComplaintChatRead(caseId, channel, lastMessageId)
          .then(() => onReadRef.current?.()).catch(() => {})
      }
    }
    markVisible()
    document.addEventListener('visibilitychange', markVisible)
    return () => document.removeEventListener('visibilitychange', markVisible)
  }, [caseId, channel, lastMessageId])

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    const body = text.trim()
    if (!body || sending || completed) return
    setSending(true)
    setSendError(null)
    try {
      await sendComplaintChatMessage(caseId, channel, body)
      setText('')
      void refresh()
    } catch (e) {
      setSendError(e instanceof Error ? e.message : '메시지를 보내지 못했습니다')
    } finally {
      setSending(false)
    }
  }

  return (
    <section className="complaint-chat-screen">
      <button type="button" className="back" onClick={onBack}>‹ 채팅 목록</button>
      <div className="complaint-page-heading">
        <div className="eyebrow">CASE #{caseId} · {channel === 'parent' ? '학부모 채팅' : '교사 채팅'}</div>
        <h2>{counterpartName}님과의 대화</h2>
        <p className="sub">{completed ? '처리 완료 · 이전 대화만 볼 수 있습니다' : '진행 중 · 민원담당자와 직접 대화합니다'}</p>
      </div>
      {!loaded && !error && <p className="loading">대화 불러오는 중</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      {loaded && visibleMessages.length === 0 && <p className="empty">아직 주고받은 메시지가 없습니다.</p>}
      <ol className="complaint-chat-log">
        {visibleMessages.map((message) => (
          <li key={message.id} className={`complaint-chat-message ${message.author_role}`}>
            <div className="complaint-chat-meta">
              <strong>{message.author_name}</strong>
              <time dateTime={message.created_at}>{formatTime(message.created_at)}</time>
            </div>
            <p>{message.text}</p>
          </li>
        ))}
      </ol>
      {sendError && <p className="alert" role="alert">{sendError}</p>}
      {completed ? (
        <p className="info">처리 완료된 민원은 채팅을 읽을 수만 있습니다.</p>
      ) : (
        <form className="complaint-chat-form" onSubmit={(event) => void onSubmit(event)}>
          <label htmlFor={`complaint-message-${channel}-${caseId}`}>메시지</label>
          <textarea
            id={`complaint-message-${channel}-${caseId}`}
            value={text}
            onChange={(event) => setText(event.target.value)}
            maxLength={3000}
            placeholder={session?.role === 'complaint_team'
              ? `${channel === 'parent' ? '학부모' : '교사'}와 대화할 내용을 입력해주세요`
              : '민원담당자와 대화할 내용을 입력해 주세요'}
            disabled={sending}
            rows={3}
          />
          <button type="submit" className="primary" disabled={sending || !text.trim()}>
            {sending ? '전송 중…' : '메시지 보내기'}
          </button>
        </form>
      )}
    </section>
  )
}
