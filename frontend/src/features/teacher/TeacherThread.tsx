import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../../api/client'
import { closeConversation, deleteConversation, extractAgain } from '../../api/conversations'
import { refineMessage, sendMessage } from '../../api/messages'
import { listTasks } from '../../api/tasks'
import type { Conversation, Task } from '../../api/types'
import { useConversationSync } from '../../realtime/useConversationSync'
import { formatTime } from '../chat/formatTime'
import { parentLabel } from '../chat/chatTitle'
import MessageForm, { type MessageFormHandle } from '../chat/MessageForm'
import NewMessageButton from '../chat/NewMessageButton'
import { teacherView } from '../chat/messageText'
import { useConversation } from '../chat/useConversation'
import { useChatScroll } from '../chat/useChatScroll'
import { useMarkRead } from '../chat/useMarkRead'
import { useMessages } from '../chat/useMessages'
import { useResource } from '../chat/useResource'
import { revealElement, revealRef } from '../chat/useReveal'
import CandidatePanel from '../tasks/CandidatePanel'
import ReplyDraftPanel, { DraftToggle } from './ReplyDraftPanel'
import ShareFromChat, { type ShareResult } from './ShareFromChat'
import { MemoPanel, MemoToggle } from './StudentMemo'
import { useStudentMemo } from './useStudentMemo'

const NO_TASKS: Task[] = []

// 교사 대화방. 대화를 바꾸면 부모가 key 로 새로 만들어 이전 대화의 글이 남지 않는다.
// onLeave: 권한이 없거나(403) 대화를 찾을 수 없을 때(404) 목록으로 돌아간다 (명세 3.1).
// onBack: "‹ 대화 목록" 으로 돌아간다.
// onDeleted: 종료된 대화를 지운 뒤 (목록에서 빼고 돌아간다)
export default function TeacherThread({
  conversation: initial,
  onLeave,
  onBack,
  onDeleted,
  deleted = false,
}: {
  conversation: Conversation
  onLeave: (message: string) => void
  onBack: () => void
  onDeleted: (id: number) => void
  deleted?: boolean // 내 목록에서 지운 대화를 다시 보는 중 (학생 탭 「삭제한 대화」) — 「대화 삭제」 버튼을 숨긴다
}) {
  const { conversation, setConversation, refresh: refreshConversation } = useConversation(initial)
  const { messages, loading, error, upsert, refresh: refreshMessages } = useMessages(initial.id)
  useMarkRead(initial.id, messages)

  const closed = conversation.status === 'closed'
  // 대화를 열면 맨 아래로, 새 글이 오면 아래를 보는 중일 때만 따라가고 위를 보는 중이면 「새 메시지」 버튼
  const { logRef, showNew, scrollToBottom } = useChatScroll(messages, (m) => m.sender_id === conversation.teacher_id)

  // 후보는 종료된 대화에서만 읽는다 (열린 대화에는 후보가 없으므로 요청을 아낀다).
  // 추출이 끝나면 서버가 알림을 보내 refreshAll 이 불리고, 그때 최신 closed 값으로 읽는다.
  const closedRef = useRef(closed)
  useEffect(() => {
    closedRef.current = closed
  })
  const loadCandidates = useCallback(async () => {
    if (!closedRef.current) return NO_TASKS
    const filter = { status: 'candidate' as const, conversationId: initial.id }
    const [todos, events] = await Promise.all([listTasks('todo', filter), listTasks('event', filter)])
    return [...todos, ...events]
  }, [initial.id])
  const {
    data: candidates,
    setData: setCandidates,
    loaded: candidatesLoaded,
    error: candidatesError,
    refresh: refreshCandidates,
  } = useResource(loadCandidates, NO_TASKS)

  const refreshAll = useCallback(() => {
    void refreshMessages()
    void refreshConversation()
    void refreshCandidates()
  }, [refreshMessages, refreshConversation, refreshCandidates])
  useConversationSync(initial.id, refreshAll)

  const formRef = useRef<MessageFormHandle>(null)
  const [sentCount, setSentCount] = useState(0)
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [closing, setClosing] = useState(false)
  const [draftOpen, setDraftOpen] = useState(false) // 「AI 초안」 메모 칸
  const [faqOpen, setFaqOpen] = useState(false) // 「공지 · Q&A」: 이 대화에서 나온 내용을 자주 묻는 질문 · 공지로
  const [shared, setShared] = useState<ShareResult | null>(null)
  const [memoOpen, setMemoOpen] = useState(false) // 학생 메모 칸
  const memo = useStudentMemo(conversation.student_id ?? null) // 「대화 종료」를 눌러 고르는 중 (뽑고 닫기 · 그냥 닫기)
  const busyRef = useRef(false) // 연타로 같은 동작이 두 번 나가는 것을 막는다

  // 종료, 다시 뽑기, 다시 정제가 함께 쓰는 실행기. 오류는 3.1 표대로 문장을 보여 주고, 403·404 는 목록으로 돌아간다.
  async function run(action: () => Promise<void>) {
    if (busyRef.current) return
    busyRef.current = true
    setBusy(true)
    setActionError(null)
    try {
      await action()
    } catch (e) {
      const message = e instanceof Error ? e.message : '요청에 실패했습니다'
      if (e instanceof ApiError && (e.status === 403 || e.status === 404)) onLeave(message)
      else setActionError(message)
    } finally {
      busyRef.current = false
      setBusy(false)
    }
  }

  // extract: true = 할 일·일정 후보를 뽑으며 닫기, false = 닫기만 (나중에 「할 일·일정 뽑기」로 뽑을 수 있음)
  const onClose = (extract: boolean) => {
    setClosing(false)
    void run(async () => {
      const closedConversation = await closeConversation(conversation.id, extract)
      justClosedRef.current = extract // 뽑으며 닫았으면 추출 결과가 보이는 곳으로 화면을 옮긴다 (아래 effect)
      setConversation(closedConversation)
      refreshAll()
    })
  }

  // 방금 닫은 대화: 추출 중 · 실패는 상태 줄로, 끝나면 후보 영역으로 스크롤한다 (이미 보이면 움직이지 않는다)
  const justClosedRef = useRef(false)
  const statusBoxRef = useRef<HTMLDivElement>(null)
  const candidateBoxRef = useRef<HTMLDivElement>(null)
  const extractStatus = closed ? (conversation.extract?.status ?? null) : null
  useEffect(() => {
    if (!justClosedRef.current || extractStatus === null) return
    if (extractStatus === 'done') revealElement(candidateBoxRef.current)
    else revealElement(statusBoxRef.current)
    if (extractStatus !== 'pending') justClosedRef.current = false
  }, [extractStatus])

  const onDelete = () => {
    if (!window.confirm('이 대화를 목록에서 삭제할까요?')) return
    void run(async () => {
      await deleteConversation(conversation.id)
      onDeleted(conversation.id)
    })
  }

  const onExtractAgain = () =>
    void run(async () => {
      setConversation(await extractAgain(conversation.id))
      refreshAll()
    })

  const onRefine = (messageId: number) =>
    void run(async () => {
      upsert(await refineMessage(conversation.id, messageId)) // pending 으로 바뀐 메시지. 결과는 S3 의 갱신으로 온다
      refreshAll()
    })

  // 교사의 답장 (status 는 서버가 skip 으로 둔다)
  async function onSend(text: string) {
    upsert(await sendMessage(conversation.id, text))
    setSentCount((n) => n + 1)
    setDraftOpen(false)
    refreshAll()
  }

  const extract = conversation.extract

  return (
    <section className="chat-screen">
      {/* 머리 한 줄: ‹ · 아바타 · 이름 ··· 메모 · 종료 (메시지 앱처럼) */}
      <div className="chat-bar">
        <button type="button" className="bar-back" onClick={onBack} aria-label="대화 목록으로">
          ‹
        </button>
        <span className="avatar">{conversation.student_name.slice(0, 1)}</span>
        <b className="bar-title">
          {parentLabel(conversation).name}
          {parentLabel(conversation).sub && <small className="bar-sub">{parentLabel(conversation).sub}</small>}
        </b>
        <span className="bar-actions">
          {conversation.student_id != null && (
            <MemoToggle open={memoOpen} onToggle={() => setMemoOpen((o) => !o)} />
          )}
          <button
            type="button"
            className={`head-action faq-toggle${faqOpen ? ' on' : ''}`}
            onClick={() => {
              setFaqOpen((o) => !o)
              setShared(null)
            }}
            aria-expanded={faqOpen}
            title="이 대화 내용으로 자주 묻는 질문 · 공지 만들기"
          >
            공지 · Q&A
          </button>
          {closed ? (
            <span className="tag">종료됨</span>
          ) : (
            <button type="button" className="head-action" onClick={() => setClosing((v) => !v)} disabled={busy}>
              종료
            </button>
          )}
        </span>
      </div>
      {!closed && closing && (
        <div className="close-choice" role="group" aria-label="대화 종료 방법" ref={revealRef}>
          <p className="info">대화를 종료할까요? 할 일·일정 후보는 종료한 뒤에도 뽑을 수 있습니다.</p>
          <button type="button" className="primary" onClick={() => onClose(true)} disabled={busy}>
            종료하고 할 일·일정 뽑기
          </button>
          <button type="button" className="outline" onClick={() => onClose(false)} disabled={busy}>
            그냥 종료
          </button>
          <button type="button" className="back" onClick={() => setClosing(false)}>
            취소
          </button>
        </div>
      )}
      {faqOpen && (
        <ShareFromChat
          conversationId={conversation.id}
          onDone={(r) => {
            setFaqOpen(false)
            setShared(r)
          }}
          onCancel={() => setFaqOpen(false)}
        />
      )}
      {shared && (
        <p className="info faq-saved" role="status">
          {shared === 'faq' ? '자주 묻는 질문에 등록했어요.' : shared === 'notice-sent' ? '공지를 게시했어요.' : '공지를 임시 저장했어요.'}{' '}
          <Link to={shared === 'faq' ? '/teacher/notices/faq' : '/teacher/notices'}>보러 가기 ›</Link>
        </p>
      )}
      {conversation.student_id != null && memoOpen && <MemoPanel memo={memo} studentName={conversation.student_name} />}

      {closed && !extract && (
        <button type="button" className="outline" onClick={onExtractAgain} disabled={busy}>
          할 일·일정 뽑기
        </button>
      )}
      {closed && extract && (
        <div ref={statusBoxRef}>
          {extract.status === 'pending' && (
            <p className="info">
              <span className="spinner blue" />
              할 일·일정 추출 중
            </p>
          )}
          {extract.status === 'done' && (
            <p className="info">할 일·일정 추출 완료{typeof extract.count === 'number' && ` (${extract.count}개)`}</p>
          )}
          {extract.status === 'failed' && (
            <>
              <p className="alert" role="alert">할 일·일정 추출 실패{extract.error && ` (${extract.error})`}</p>
              <button type="button" className="outline" onClick={onExtractAgain} disabled={busy}>
                다시 뽑기
              </button>
            </>
          )}
        </div>
      )}
      {actionError && <p className="alert" role="alert" ref={revealRef}>{actionError}</p>}
      {loading && <p className="loading">불러오는 중</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      {!loading && !error && messages.length === 0 && (
        <div className="empty">
          <div className="big">▤</div>아직 메시지가 없어요
        </div>
      )}

      <ul className="chat-log" ref={logRef}>
        {messages.map((m) => {
          // sender_id 가 대화의 teacher_id 와 같으면 교사 글(내 글) (중대 4)
          const mine = m.sender_id === conversation.teacher_id
          const view = teacherView(m)
          return (
            <li key={m.id} className={`chat-message ${mine ? 'mine' : ''}`}>
              <div className="chat-name">
                {mine ? '나' : parentLabel(conversation).name} <span>{formatTime(m.created_at)}</span>
              </div>
              {view.kind === 'text' && <div className="chat-bubble">{view.text}</div>}
              {view.kind === 'pending' && (
                <div className="chat-bubble">
                  <span className="spinner blue" />
                  정제 중
                </div>
              )}
              {view.kind === 'failed' && (
                <>
                  <div className="chat-bubble">
                    정제 실패
                    {view.reason && ` (${view.reason})`}
                  </div>
                  <div className="msg-actions">
                    <button type="button" className="item-edit" onClick={() => onRefine(m.id)} disabled={busy}>
                      다시 정제
                    </button>
                  </div>
                </>
              )}
              {view.kind === 'empty' && <div className="chat-bubble">표시할 수 있는 내용이 없습니다</div>}
            </li>
          )
        })}
      </ul>

      {/* 종료된 대화에는 입력창을 숨긴다: 서버가 종료된 대화의 글을 막는다 (409) */}
      {closed ? (
        <>
          <div className="closed-note">{deleted ? '종료하고 목록에서 삭제한 대화입니다.' : '이 대화는 종료되었습니다.'}</div>
          <div ref={candidateBoxRef}>
            <CandidatePanel
              candidates={candidates}
              loading={!candidatesLoaded && candidatesError === null}
              error={candidatesError}
              onUpdated={(t) => setCandidates((prev) => prev.map((p) => (p.id === t.id ? t : p)))}
              onRemoved={(id) => setCandidates((prev) => prev.filter((p) => p.id !== id))}
            />
          </div>
          {!deleted && (
            <button type="button" className="delete-item" onClick={onDelete} disabled={busy}>
              대화 삭제
            </button>
          )}
        </>
      ) : (
        <>
          {/* 초안은 입력창에 채워질 뿐 자동으로 보내지 않는다. 보내면 패널을 새로 만들어 이전 초안의 확인 항목을 지운다 (S7) */}
          {/* 입력창은 화면 아래에 붙어 있다 (메시지가 길어도 스크롤해도 보임) */}
          <div className="chat-compose">
            <NewMessageButton visible={showNew} onClick={() => scrollToBottom()} />
            <MessageForm
              id="teacher-reply"
              label="답장 쓰기"
              onSend={onSend}
              handleRef={formRef}
              headerAction={<DraftToggle open={draftOpen} onToggle={() => setDraftOpen((o) => !o)} />}
              beforeInput={
                <ReplyDraftPanel key={sentCount} conversationId={conversation.id} formRef={formRef} open={draftOpen} />
              }
            />
          </div>
        </>
      )}
    </section>
  )
}
