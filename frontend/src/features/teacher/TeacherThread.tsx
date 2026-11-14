import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../../api/client'
import { closeConversation, extractAgain } from '../../api/conversations'
import { refineMessage, sendMessage } from '../../api/messages'
import { listTasks } from '../../api/tasks'
import type { Conversation, Task } from '../../api/types'
import { useConversationSync } from '../../realtime/useConversationSync'
import { formatTime } from '../chat/formatTime'
import MessageForm, { type MessageFormHandle } from '../chat/MessageForm'
import { teacherView } from '../chat/messageText'
import { useConversation } from '../chat/useConversation'
import { useMessages } from '../chat/useMessages'
import { useResource } from '../chat/useResource'
import CandidatePanel from '../tasks/CandidatePanel'
import ReplyDraftPanel from './ReplyDraftPanel'

const NO_TASKS: Task[] = []

// 교사 대화방. 대화를 바꾸면 부모가 key 로 새로 만들어 이전 대화의 글이 남지 않는다.
// onLeave: 권한이 없거나(403) 대화를 찾을 수 없을 때(404) 목록으로 돌아간다 (명세 3.1).
// onBack: "‹ 대화 목록" 으로 돌아간다.
export default function TeacherThread({
  conversation: initial,
  onLeave,
  onBack,
}: {
  conversation: Conversation
  onLeave: (message: string) => void
  onBack: () => void
}) {
  const { conversation, setConversation, refresh: refreshConversation } = useConversation(initial)
  const { messages, loading, error, upsert, refresh: refreshMessages } = useMessages(initial.id)

  const closed = conversation.status === 'closed'

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

  const onClose = () => {
    if (!window.confirm('대화를 종료할까요? 종료하면 할 일과 일정 후보를 뽑습니다.')) return
    void run(async () => {
      setConversation(await closeConversation(conversation.id))
      refreshAll()
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
    refreshAll()
  }

  const extract = conversation.extract

  return (
    <section>
      <div className="chat-head">
        <button type="button" className="back" onClick={onBack}>
          ‹ 대화 목록
        </button>
        <span className="tag">{closed ? '종료된 대화' : '대화 중'}</span>
      </div>
      <div className="chat-person">
        <span className="avatar">{conversation.student_name.slice(0, 1)}</span>
        <div>
          <b>{conversation.student_name}</b>
        </div>
      </div>

      {closed && extract && (
        <div>
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
      {actionError && <p className="alert" role="alert">{actionError}</p>}
      {loading && <p className="loading">불러오는 중</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      {!loading && !error && messages.length === 0 && (
        <div className="empty">
          <div className="big">▤</div>아직 메시지가 없어요
        </div>
      )}

      <ul className="chat-log">
        {messages.map((m) => {
          // sender_id 가 대화의 teacher_id 와 같으면 교사 글(내 글) (중대 4)
          const mine = m.sender_id === conversation.teacher_id
          const view = teacherView(m)
          return (
            <li key={m.id} className={`chat-message ${mine ? 'mine' : ''}`}>
              <div className="chat-name">
                {mine ? '나' : '학부모'} <span>{formatTime(m.created_at)}</span>
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

      {/* 종료된 대화에는 교사의 입력창을 숨긴다: 서버는 누가 보내든 대화를 다시 열기 때문 (경미 6) */}
      {closed ? (
        <>
          <div className="closed-note">이 대화는 종료되었습니다.</div>
          <CandidatePanel
            candidates={candidates}
            loading={!candidatesLoaded && candidatesError === null}
            error={candidatesError}
            onUpdated={(t) => setCandidates((prev) => prev.map((p) => (p.id === t.id ? t : p)))}
            onRemoved={(id) => setCandidates((prev) => prev.filter((p) => p.id !== id))}
          />
        </>
      ) : (
        <>
          {/* 초안은 입력창에 채워질 뿐 자동으로 보내지 않는다. 보내면 패널을 새로 만들어 이전 초안의 확인 항목을 지운다 (S7) */}
          <ReplyDraftPanel key={sentCount} conversationId={conversation.id} formRef={formRef} />
          <MessageForm
            id="teacher-reply"
            label="답장"
            onSend={onSend}
            handleRef={formRef}
            extraAction={
              <button type="button" className="end" onClick={onClose} disabled={busy}>
                대화 종료
              </button>
            }
          />
          <div className="info">대화를 종료하면 할 일과 일정 후보를 정리합니다.</div>
        </>
      )}
    </section>
  )
}
