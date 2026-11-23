import { useState, type FormEvent } from 'react'
import { listComplaints, submitComplaint } from '../../api/complaints'
import type { ComplaintCaseSummary, ComplaintChatSummary, ComplaintStatus } from '../../api/types'
import { useSync } from '../../realtime/useSync'
import { formatTime } from '../chat/formatTime'
import { parentTitle } from '../chat/chatTitle'
import { useConversations } from '../chat/useConversations'
import { useResource } from '../chat/useResource'
import ComplaintChatThread from './ComplaintChatThread'

const EMPTY: ComplaintCaseSummary[] = []
const STATUS_LABEL: Record<ComplaintStatus, string> = {
  received: '접수됨',
  in_progress: '진행 중',
  completed: '처리 완료',
}
const STATUSES: ComplaintStatus[] = ['received', 'in_progress', 'completed']

export default function TeacherComplaints({ chats, chatsLoaded, chatsError, refreshChats }: {
  chats: ComplaintChatSummary[]
  chatsLoaded: boolean
  chatsError: string | null
  refreshChats: () => void
}) {
  const { conversations, loading: conversationsLoading, error: conversationsError } = useConversations()
  const { data: cases, setData: setCases, loaded, error, refresh } = useResource(listComplaints, EMPTY)
  useSync('teacher-complaints', refresh, (event) => event.type === 'complaints')
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [successId, setSuccessId] = useState<number | null>(null)
  const [filter, setFilter] = useState<ComplaintStatus>('received')
  const [chatCase, setChatCase] = useState<{ id: number; status: Exclude<ComplaintStatus, 'received'> } | null>(null)

  const selectedParent = conversations.find((conversation) => selectedIds.includes(conversation.id))?.parent_id
  const choices = conversations.filter((conversation) => conversation.last_message_at)
  const filteredCases = cases.filter((complaint) => complaint.status === filter)
  const unreadChats = chats.reduce((count, chat) => count + (chat.unread_count ?? 0), 0)
  const sortedChats = [...chats].sort((a, b) => {
    const unreadDifference = Number((b.unread_count ?? 0) > 0) - Number((a.unread_count ?? 0) > 0)
    return unreadDifference || (b.last_message_at || '').localeCompare(a.last_message_at || '')
  })

  function toggleConversation(id: number) {
    setSelectedIds((old) => old.includes(id) ? old.filter((value) => value !== id) : [...old, id])
    setSubmitError(null)
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    const body = reason.trim()
    if (submitting) return
    if (selectedIds.length === 0) {
      setSubmitError('이관할 대화를 하나 이상 선택해 주세요.')
      return
    }
    if (!body) {
      setSubmitError('부당한 요구로 느낀 이유와 불편했던 점을 적어 주세요.')
      return
    }
    setSubmitting(true)
    setSubmitError(null)
    try {
      const complaint = await submitComplaint(selectedIds, body)
      setCases((old) => [complaint, ...old.filter((item) => item.id !== complaint.id)])
      setSelectedIds([])
      setReason('')
      setSuccessId(complaint.id)
      setFilter('received')
      void refresh()
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : '민원 이관 신청을 보내지 못했습니다.')
    } finally {
      setSubmitting(false)
    }
  }

  if (chatCase) {
    return (
      <ComplaintChatThread
        caseId={chatCase.id}
        channel="teacher"
        counterpartName="민원담당자"
        status={cases.find((item) => item.id === chatCase.id)?.status === 'completed' || chats.find((item) => item.case_id === chatCase.id)?.status === 'completed' || chatCase.status === 'completed' ? 'completed' : 'in_progress'}
        onBack={() => { setChatCase(null); void refreshChats() }}
        onRead={refreshChats}
      />
    )
  }

  return (
    <section className="complaint-page teacher-complaints">
      <div className="teacher-support-entry">
        <div className="teacher-support-heading">
          <h2>담당자와의 채팅</h2>
          {unreadChats > 0 && <span className="badge complaint-unread-badge" aria-label={`새 메시지 ${unreadChats}개`}>{unreadChats > 99 ? '99+' : unreadChats}</span>}
        </div>
        <p className="sub">민원담당자에게서 온 메시지를 확인하고 답장할 수 있습니다.</p>
        {!chatsLoaded && !chatsError && <p className="loading">담당자 채팅 불러오는 중</p>}
        {chatsError && <p className="alert" role="alert">{chatsError}</p>}
        {chatsLoaded && !chatsError && sortedChats.length === 0 && <p className="empty">담당자가 신청서를 열면 이곳에서 채팅할 수 있습니다.</p>}
        <div className="teacher-support-list">
          {sortedChats.map((chat) => (
            <button key={chat.case_id} type="button" className="teacher-support-chat" onClick={() => setChatCase({ id: chat.case_id, status: chat.status })}>
              <span className="teacher-support-chat-title">
                <strong>민원 #{chat.case_id} · 담당자와 채팅</strong>
                {chat.unread_count > 0 && <span className="badge complaint-unread-badge" aria-label={`새 메시지 ${chat.unread_count}개`}>{chat.unread_count > 99 ? '99+' : chat.unread_count}</span>}
              </span>
              <span className="teacher-support-preview">{chat.last_message_text || '담당자와 대화를 시작하세요.'}</span>
              <small>{chat.status === 'completed' ? '처리 완료 · 이전 대화 보기' : '진행 중 · 대화 열기'}{chat.last_message_at ? ` · ${formatTime(chat.last_message_at)}` : ''}</small>
            </button>
          ))}
        </div>
      </div>
      <div className="eyebrow">COMPLAINT HANDOFF</div>
      <h2>민원 이관</h2>
      <p className="sub">말투 정제를 넘어 부당한 요구로 느껴진 대화를 민원담당자에게 전달할 수 있습니다.</p>
      <div className="report-policy">
        <b>선택한 대화의 원문도 담당자에게 전달됩니다.</b>
        <p>교사에게는 정제되어 보였던 학부모 메시지도 담당자는 원문과 함께 확인합니다. 신청 사유와 대화 내용을 토대로 AI가 근거 보고서를 작성합니다.</p>
      </div>

      <form className="complaint-form" onSubmit={(event) => void onSubmit(event)}>
        <h3>새 이관 신청</h3>
        <p className="info">같은 학부모와의 대화를 여러 개 선택할 수 있습니다. 진행 중·종료된 대화 모두 포함됩니다.</p>
        {conversationsLoading && <p className="loading">대화 불러오는 중</p>}
        {conversationsError && <p className="alert" role="alert">{conversationsError}</p>}
        {!conversationsLoading && choices.length === 0 && <p className="empty">신청에 포함할 대화가 없습니다.</p>}
        <fieldset className="complaint-choices" disabled={submitting}>
          <legend>이관할 대화 선택</legend>
          {choices.map((conversation) => {
            const checked = selectedIds.includes(conversation.id)
            const disabled = !checked && (
              (selectedParent !== undefined && selectedParent !== conversation.parent_id) || selectedIds.length >= 20
            )
            return (
              <label key={conversation.id} className={`complaint-choice${checked ? ' selected' : ''}${disabled ? ' disabled' : ''}`}>
                <input type="checkbox" checked={checked} disabled={disabled} onChange={() => toggleConversation(conversation.id)} />
                <span className="complaint-choice-main">
                  <strong>{parentTitle(conversation)}</strong>
                  <span>{conversation.preview?.summary || conversation.preview?.last?.text || `대화 #${conversation.id}`}</span>
                  <small>{conversation.status === 'open' ? '진행 중' : '종료됨'} · {formatTime(conversation.last_message_at || conversation.created_at)}</small>
                </span>
              </label>
            )
          })}
        </fieldset>
        {selectedParent !== undefined && <p className="complaint-hint">다른 학부모의 대화를 고르려면 현재 선택을 해제해 주세요. 신청서당 최대 20개 대화입니다.</p>}
        <label className="editor-label" htmlFor="complaint-reason">이관 사유 · 불편했던 점</label>
        <textarea
          id="complaint-reason"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          placeholder="어떤 요구가 부당하다고 느껴졌는지, 업무에서 어떤 어려움이 있었는지 구체적으로 적어 주세요."
          rows={6}
          maxLength={2000}
          disabled={submitting}
          required
        />
        <small className="complaint-hint">{reason.length}/2000자 · 신청 사유는 학부모에게 공개되지 않습니다.</small>
        {submitError && <p className="alert" role="alert">{submitError}</p>}
        <button type="submit" className="primary" disabled={submitting || selectedIds.length === 0 || !reason.trim()}>
          {submitting ? '신청 중…' : `${selectedIds.length}개 대화 민원 이관 신청`}
        </button>
      </form>

      {successId !== null && <p className="report-receipt" role="status">민원 #{successId} 신청이 접수되었습니다. 담당자가 신청서를 열면 진행 중으로 바뀝니다.</p>}
      <div className="complaint-page-heading">
        <h3>내 이관 신청</h3>
        {!loaded && !error && <p className="loading">신청 내역 불러오는 중</p>}
      </div>
      {error && <p className="alert" role="alert">{error}</p>}
      <div className="complaint-status-tabs" role="group" aria-label="민원 진행 상태">
        {STATUSES.map((status) => (
          <button key={status} type="button" className={filter === status ? 'active' : ''} onClick={() => setFilter(status)}>
            {STATUS_LABEL[status]} <span>{cases.filter((item) => item.status === status).length}</span>
          </button>
        ))}
      </div>
      {loaded && filteredCases.length === 0 && <p className="empty">{STATUS_LABEL[filter]} 신청이 없습니다.</p>}
      <ul className="plain-list complaint-case-list">
        {filteredCases.map((complaint) => (
          <li key={complaint.id} className="report-card">
            <div className="report-card-top">
              <span className="tag">{STATUS_LABEL[complaint.status]}</span>
              <small>{formatTime(complaint.created_at)}</small>
            </div>
            <h3>민원 #{complaint.id} · {complaint.parent_name} 학부모</h3>
            <p>{complaint.reason}</p>
            <small>선택 대화 {complaint.conversation_ids.length}건</small>
            {complaint.status !== 'received' && (
              <button type="button" className="outline complaint-chat-open" onClick={() => setChatCase({ id: complaint.id, status: complaint.status === 'completed' ? 'completed' : 'in_progress' })}>
                담당자와 채팅 ›
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
