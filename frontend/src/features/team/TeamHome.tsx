import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { Link, Navigate, Route, Routes, useSearchParams } from 'react-router-dom'
import { completeComplaint, getComplaint, listComplaintChats, listComplaints, retryComplaintReport } from '../../api/complaints'
import type { ComplaintCaseDetail, ComplaintCaseSummary, ComplaintChannel, ComplaintChatSummary, ComplaintEvidence, ComplaintReport, ComplaintStatus } from '../../api/types'
import AppShell from '../../components/AppShell'
import BottomNav, { type NavItem } from '../../components/BottomNav'
import { ChatIcon, ComplaintIcon } from '../../components/icons'
import { useSync } from '../../realtime/useSync'
import { formatTime } from '../chat/formatTime'
import { useResource } from '../chat/useResource'
import ComplaintChatThread from '../complaints/ComplaintChatThread'

const EMPTY_CASES: ComplaintCaseSummary[] = []
const EMPTY_CHATS: ComplaintChatSummary[] = []
const STATUS_LABEL: Record<ComplaintStatus, string> = { received: '접수됨', in_progress: '진행 중', completed: '처리 완료' }
const CASE_STATUSES: ComplaintStatus[] = ['received', 'in_progress', 'completed']
const CHAT_STATUSES: Exclude<ComplaintStatus, 'received'>[] = ['in_progress', 'completed']

// 민원담당자는 일반 교사·학부모 화면과 분리된 전용 메뉴로 들어온다.
export default function TeamHome() {
  const nav: NavItem[] = [
    { to: '/team', label: '신청서', icon: <ComplaintIcon />, end: true },
    { to: '/team/parent-chats', label: '학부모채팅', icon: <ChatIcon /> },
    { to: '/team/teacher-chats', label: '교사채팅', icon: <ChatIcon /> },
  ]
  return (
    <AppShell title="민원담당자" nav={<BottomNav items={nav} label="민원담당자 메뉴" />}>
      <Routes>
        <Route index element={<TeamApplications />} />
        <Route path="parent-chats" element={<TeamChatTab channel="parent" />} />
        <Route path="teacher-chats" element={<TeamChatTab channel="teacher" />} />
        <Route path="*" element={<Navigate to="/team" replace />} />
      </Routes>
    </AppShell>
  )
}

function TeamApplications() {
  const { data: cases, loaded, error, refresh } = useResource(listComplaints, EMPTY_CASES)
  useSync('team-complaints', refresh, (event) => event.type === 'complaints')
  const [filter, setFilter] = useState<ComplaintStatus>('received')
  const [params, setParams] = useSearchParams()
  const selectedId = Number(params.get('case')) || null
  if (selectedId !== null) {
    return <TeamApplicationDetail key={selectedId} caseId={selectedId} onBack={() => {
      setParams({})
      void refresh()
    }} />
  }
  const shown = cases.filter((complaint) => complaint.status === filter)
  return (
    <section className="complaint-page">
      <div className="eyebrow">SCHOOL SUPPORT TEAM</div>
      <h2>민원 이관 신청서</h2>
      <p className="sub">교사가 선택한 대화와 신청 사유를 확인합니다. 신청서를 열면 진행 중으로 변경됩니다.</p>
      {!loaded && !error && <p className="loading">신청서 불러오는 중</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      <div className="complaint-status-tabs" role="group" aria-label="신청서 상태">
        {CASE_STATUSES.map((status) => <button key={status} type="button" className={filter === status ? 'active' : ''} onClick={() => setFilter(status)}>
          {STATUS_LABEL[status]} <span>{cases.filter((item) => item.status === status).length}</span>
        </button>)}
      </div>
      {loaded && shown.length === 0 && <p className="empty">{STATUS_LABEL[filter]} 신청서가 없습니다.</p>}
      <ul className="plain-list complaint-case-list">
        {shown.map((complaint) => <li key={complaint.id}>
          <button type="button" className="report-card" onClick={() => setParams({ case: String(complaint.id) })}>
            <span className="report-card-top"><span className="tag">{STATUS_LABEL[complaint.status]}</span><small>{formatTime(complaint.created_at)}</small></span>
            <h3>#{complaint.id} · {complaint.teacher_name} 선생님</h3>
            <p>{complaint.parent_name} 학부모 · 대화 {complaint.conversation_ids.length}건</p>
            <small>{complaint.report_status === 'pending' ? 'AI 보고서 작성 중' : complaint.report_status === 'failed' ? 'AI 보고서 작성 실패' : '보고서 보기 ›'}</small>
          </button>
        </li>)}
      </ul>
    </section>
  )
}

function EvidenceReference({ evidence, children }: { evidence: ComplaintEvidence; children?: ReactNode }) {
  return <li><a href={`#complaint-message-${evidence.message_id}`} onClick={() => {
    const message = document.getElementById(`complaint-message-${evidence.message_id}`)
    const thread = message?.closest('details')
    if (thread instanceof HTMLDetailsElement) thread.open = true
  }}>
    대화 #{evidence.conversation_id} · 메시지 #{evidence.message_id} · {formatTime(evidence.at)} ↗
  </a><p>“{evidence.quote}”</p>{children}</li>
}

function ReportView({ report, conversationCount }: {
  report: ComplaintReport
  conversationCount: number
}) {
  const [openEvidence, setOpenEvidence] = useState<'rude' | 'repeated' | null>(null)
  const toggleEvidence = (kind: 'rude' | 'repeated') => {
    setOpenEvidence((current) => current === kind ? null : kind)
  }

  return <section className="complaint-report" aria-label="AI 민원 근거 보고서">
    <div className="complaint-report-heading">
      <span className="eyebrow">AI EVIDENCE REPORT</span>
      <h3>AI 민원 근거 보고서</h3>
      <p>교사의 신청 사유와 학부모 원문을 비교해 확인된 내용을 정리했습니다.</p>
    </div>
    <div className="complaint-report-summary">
      <h4>대화 요약</h4>
      <p>{report.summary}</p>
    </div>
    <section className="complaint-reason-evidence" aria-labelledby="complaint-reason-evidence-title">
      <div className="complaint-evidence-heading">
        <span className="tag">핵심 근거</span>
        <h4 id="complaint-reason-evidence-title">교사 신청 사유를 뒷받침하는 대화</h4>
      </div>
      {report.reason_evidence.length === 0 ? <p className="info">대화 원문에서 직접 확인된 근거가 없습니다. 교사가 적은 사유와 원문 기록을 함께 검토해 주세요.</p> :
        <ol className="report-evidence complaint-reason-list">{report.reason_evidence.map((evidence) => <EvidenceReference key={`${evidence.message_id}-${evidence.quote}`} evidence={evidence}>
          <p className="complaint-evidence-explanation">{evidence.explanation}</p></EvidenceReference>)}</ol>}
    </section>
    <div className="report-metrics complaint-metrics" aria-label="분석 건수">
      <div><strong>{conversationCount}</strong><span>이관한 대화</span></div>
      <button type="button" className="complaint-metric-toggle" aria-expanded={openEvidence === 'rude'}
        aria-controls="complaint-rude-evidence" onClick={() => toggleEvidence('rude')}>
        <strong>{report.rude_messages}</strong><span>거친 표현 메시지</span><small>{openEvidence === 'rude' ? '근거 닫기 ↑' : '근거 보기 ↓'}</small>
      </button>
      <button type="button" className="complaint-metric-toggle" aria-expanded={openEvidence === 'repeated'}
        aria-controls="complaint-repeated-evidence" onClick={() => toggleEvidence('repeated')}>
        <strong>{report.repeated_demands_count}</strong><span>반복 요구 메시지</span><small>{openEvidence === 'repeated' ? '근거 닫기 ↑' : '근거 보기 ↓'}</small>
      </button>
    </div>
    <section id="complaint-rude-evidence" className="complaint-secondary-evidence" aria-label="거친 표현 근거" hidden={openEvidence !== 'rude'}>
      <h4>거친 표현 근거</h4>
      {report.rude_evidence.length === 0 ? <p className="info">확인된 거친 표현 근거가 없습니다.</p> :
        <ol className="report-evidence">{report.rude_evidence.map((evidence) => <EvidenceReference key={evidence.message_id} evidence={evidence}>
          <small>{evidence.types.join(' · ')}</small></EvidenceReference>)}</ol>}
    </section>
    <section id="complaint-repeated-evidence" className="complaint-secondary-evidence" aria-label="반복된 요구와 근거" hidden={openEvidence !== 'repeated'}>
      <h4>반복된 요구와 근거</h4>
      {report.repeated_demands.length === 0 ? <p className="info">확인된 반복 요구가 없습니다.</p> : report.repeated_demands.map((item, index) =>
        <div key={`${item.theme}-${index}`} className="complaint-evidence-group"><b>{item.theme}</b>
          <ol className="report-evidence">{item.evidence.map((evidence) => <EvidenceReference key={evidence.message_id} evidence={evidence} />)}</ol>
        </div>)}
    </section>
  </section>
}

function TeamApplicationDetail({ caseId, onBack }: { caseId: number; onBack: () => void }) {
  // 담당자가 상세를 처음 읽는 GET에서만 서버가 접수됨 → 진행 중으로 원자적으로 바꾼다.
  const load = useCallback(() => getComplaint(caseId), [caseId])
  const { data: complaint, setData, loaded, error, refresh } = useResource<ComplaintCaseDetail | null>(load, null)
  useSync(`complaint-${caseId}`, refresh, (event) => event.type === 'complaints' && (event.caseId === null || event.caseId === caseId))
  const [finishing, setFinishing] = useState(false)
  const [finishError, setFinishError] = useState<string | null>(null)
  const [retrying, setRetrying] = useState(false)
  const [retryError, setRetryError] = useState<string | null>(null)
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000)
    return () => window.clearInterval(timer)
  }, [])
  const canRetry = complaint !== null && (complaint.report_status === 'failed' ||
    (complaint.report_status === 'pending' && now - Date.parse(complaint.report_requested_at) >= 10 * 60_000))

  async function finish() {
    if (finishing || !complaint || complaint.status === 'completed') return
    setFinishing(true)
    setFinishError(null)
    try {
      const updated = await completeComplaint(caseId)
      setData((old) => old ? { ...old, ...updated } : old)
    } catch (e) {
      setFinishError(e instanceof Error ? e.message : '처리 완료로 변경하지 못했습니다.')
    } finally {
      setFinishing(false)
    }
  }

  async function retry() {
    if (retrying) return
    setRetrying(true)
    setRetryError(null)
    try {
      const updated = await retryComplaintReport(caseId)
      setData((old) => old ? { ...old, ...updated, report: null, report_error: null } : old)
    } catch (e) {
      setRetryError(e instanceof Error ? e.message : '보고서를 다시 만들지 못했습니다.')
    } finally {
      setRetrying(false)
    }
  }

  return <section className="complaint-page complaint-detail">
    <button type="button" className="back" onClick={onBack}>‹ 신청서 목록</button>
    {!loaded && !error && <p className="loading">신청서 불러오는 중</p>}
    {error && <p className="alert" role="alert">{error}</p>}
    {complaint && <>
      <div className="eyebrow">CASE #{complaint.id}</div>
      <h2>민원 이관 신청서</h2>
      <p className="sub">{complaint.teacher_name} 선생님 · {complaint.parent_name} 학부모 · {formatTime(complaint.created_at)}</p>
      <span className="tag">{STATUS_LABEL[complaint.status]}</span>
      <section className="report-section complaint-submitted-reason"><h3>교사가 작성한 이관 사유</h3><p className="report-reason">{complaint.reason}</p></section>
      {complaint.report_status === 'pending' && <p className="report-policy">AI가 선택된 대화를 분석해 보고서를 작성하고 있습니다.</p>}
      {complaint.report_status === 'failed' && <p className="alert" role="alert">보고서를 작성하지 못했습니다. {complaint.report_error ?? ''}</p>}
      {canRetry && <div className="complaint-report-failed">
        <button type="button" className="outline" onClick={() => void retry()} disabled={retrying}>{retrying ? '다시 만드는 중…' : '보고서 다시 만들기'}</button>
        {retryError && <p className="alert" role="alert">{retryError}</p>}
      </div>}
      {complaint.report && <ReportView report={complaint.report}
        conversationCount={complaint.conversations.length} />}
      <section className="report-section complaint-transcript-section"><h3>선택된 대화 · 원문 기록</h3>
        <p className="info">교사에게 정제되어 보인 메시지도 여기서는 학부모 원문과 전달된 문장을 구분해 확인할 수 있습니다.</p>
        {complaint.conversations.map((conversation) => <details key={conversation.id} className="report-conversation" open>
          <summary>대화 #{conversation.id} · {conversation.student_name}
            <small>{conversation.status === 'open' ? '진행 중' : '종료됨'} · 메시지 {conversation.messages.length}건</small>
          </summary>
          {conversation.messages.map((message) => <article key={message.id} className="report-message" id={`complaint-message-${message.id}`}>
            <div className="report-message-head"><b>{message.who === 'parent' ? '학부모' : '교사'}</b><time dateTime={message.created_at}>{formatTime(message.created_at)}</time></div>
            {message.who === 'parent' ? <>
              <div className="report-original"><span>학부모 원문</span><p>{message.raw_text ?? message.text ?? '원문 없음'}</p></div>
              <div className="report-displayed"><span>교사에게 전달된 문장</span>
                <p>{message.status === 'done' ? (message.refined_text ?? message.raw_text ?? '내용 없음') : '정제 중이거나 전달되지 않은 메시지'}</p>
              </div>
            </> : <div className="report-teacher"><span>교사의 최종 답장</span><p>{message.text ?? message.raw_text ?? ''}</p></div>}
          </article>)}
        </details>)}
      </section>
      <div className="complaint-detail-actions">
        <Link to={`/team/parent-chats?case=${complaint.id}`} className="outline">학부모 채팅 ›</Link>
        <Link to={`/team/teacher-chats?case=${complaint.id}`} className="outline">교사 채팅 ›</Link>
      </div>
      {finishError && <p className="alert" role="alert">{finishError}</p>}
      {complaint.status !== 'completed' && <button type="button" className="primary" onClick={() => void finish()} disabled={finishing}>
        {finishing ? '처리 중…' : '처리 완료'}
      </button>}
    </>}
  </section>
}

function TeamChatTab({ channel }: { channel: ComplaintChannel }) {
  const load = useCallback(() => listComplaintChats(channel), [channel])
  const { data: chats, loaded, error, refresh } = useResource(load, EMPTY_CHATS)
  useSync(`team-${channel}-chats`, refresh, (event) => event.type === 'complaints')
  const [filter, setFilter] = useState<Exclude<ComplaintStatus, 'received'>>('in_progress')
  const [params, setParams] = useSearchParams()
  const selectedId = Number(params.get('case')) || null
  const selected = chats.find((chat) => chat.case_id === selectedId) ?? null
  const label = channel === 'parent' ? '학부모' : '교사'
  if (selected) return <>
    <Link className="complaint-case-jump" to={`/team?case=${selected.case_id}`}>신청서 #{selected.case_id} 바로 보기 →</Link>
    <ComplaintChatThread key={`${selected.case_id}-${channel}`} caseId={selected.case_id} channel={channel}
      counterpartName={selected.counterpart_name} status={selected.status} onBack={() => setParams({})} />
  </>
  const shown = chats.filter((chat) => chat.status === filter)
  return <section className="complaint-page">
    <div className="eyebrow">SCHOOL SUPPORT TEAM</div><h2>{label}채팅</h2>
    <p className="sub">민원 신청서별로 {label}와 직접 대화합니다. 처리 완료된 대화는 읽기만 가능합니다.</p>
    {!loaded && !error && <p className="loading">채팅 목록 불러오는 중</p>}
    {error && <p className="alert" role="alert">{error}</p>}
    <div className="complaint-status-tabs" role="group" aria-label={`${label}채팅 상태`}>
      {CHAT_STATUSES.map((status) => <button key={status} type="button" className={filter === status ? 'active' : ''} onClick={() => setFilter(status)}>
        {STATUS_LABEL[status]} <span>{chats.filter((chat) => chat.status === status).length}</span>
      </button>)}
    </div>
    {loaded && shown.length === 0 && <p className="empty">{STATUS_LABEL[filter]} {label}채팅이 없습니다.</p>}
    <ul className="plain-list complaint-case-list">{shown.map((chat) => <li key={chat.case_id}>
      <button type="button" className="report-card" onClick={() => setParams({ case: String(chat.case_id) })}>
        <span className="report-card-top"><span className="tag">{STATUS_LABEL[chat.status]}</span>
          {chat.last_message_at && <small>{formatTime(chat.last_message_at)}</small>}</span>
        <h3>#{chat.case_id} · {chat.counterpart_name}</h3>
        <p>{chat.last_message_text || '아직 주고받은 메시지가 없습니다.'}</p><small>채팅 열기 ›</small>
      </button>
      <Link className="complaint-case-jump" to={`/team?case=${chat.case_id}`}>신청서 #{chat.case_id} 보기 →</Link>
    </li>)}</ul>
  </section>
}
