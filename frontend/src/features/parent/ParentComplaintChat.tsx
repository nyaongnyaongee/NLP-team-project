import { useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { listComplaintChats } from '../../api/complaints'
import type { ComplaintChatSummary } from '../../api/types'
import { useSync } from '../../realtime/useSync'
import { formatTime } from '../chat/formatTime'
import { useResource } from '../chat/useResource'
import ComplaintChatThread from '../complaints/ComplaintChatThread'

const EMPTY: ComplaintChatSummary[] = []

// 학부모에게는 담당자와의 별도 채팅만 보인다. 교사의 신청 사유, 원문 증거, AI 보고서는 이 API에 포함되지 않는다.
export default function ParentComplaintChat() {
  const load = useCallback(() => listComplaintChats('parent'), [])
  const { data: chats, loaded, error, refresh } = useResource(load, EMPTY)
  useSync('parent-complaint-chat-list', refresh, (event) => event.type === 'complaints')

  const [params] = useSearchParams()
  const navigate = useNavigate()
  const selectedId = Number(params.get('case')) || null
  const selected = chats.find((chat) => chat.case_id === selectedId)

  if (selected) {
    return (
      <ComplaintChatThread
        caseId={selected.case_id}
        channel="parent"
        counterpartName={selected.counterpart_name || '민원 담당자'}
        status={selected.status}
        onBack={() => {
          navigate('/parent/support')
          void refresh()
        }}
      />
    )
  }

  return (
    <section>
      <div className="eyebrow">SCHOOL SUPPORT TEAM</div>
      <div className="notice-heading"><h2>민원 담당자와 대화</h2></div>
      <p className="sub">담당자가 연락한 대화가 여기에 표시됩니다.</p>
      {!loaded && !error && <p className="loading">불러오는 중</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      {loaded && !error && chats.length === 0 && <div className="empty">담당자와의 대화가 아직 없어요</div>}
      {chats.map((chat) => (
        <button
          type="button"
          className="report-card"
          key={chat.case_id}
          onClick={() => navigate(`/parent/support?case=${chat.case_id}`)}
        >
          <span className="report-card-top">
            <span className="tag">{chat.status === 'completed' ? '처리 완료' : '진행 중'}</span>
            {chat.last_message_at && <small>{formatTime(chat.last_message_at)}</small>}
          </span>
          <h3>{chat.counterpart_name || '민원 담당자'}</h3>
          <p>{chat.last_message_text || '대화를 열어 담당자에게 메시지를 보낼 수 있어요.'}</p>
        </button>
      ))}
    </section>
  )
}
