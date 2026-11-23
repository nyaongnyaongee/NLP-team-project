import { useState } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { closeConversation } from '../../api/conversations'
import ConversationList from '../chat/ConversationList'
import StartConversation from '../chat/StartConversation'
import StatusFilter from '../chat/StatusFilter'
import { revealRef } from '../chat/useReveal'
import { useStatusFilter } from '../chat/useStatusFilter'
import { useConversations } from '../chat/useConversations'
import { useOpenTodoCount } from '../tasks/useOpenTodoCount'
import TeacherDashboard from './TeacherDashboard'
import TeacherThread from './TeacherThread'

// 교사 "대화 목록" 탭 (S2~S4 의 교사 화면). 대화를 고르면 목록 대신 그 대화방이 열리고, "‹ 대화 목록"으로 돌아온다 (데모와 같은 흐름).
export default function ConversationsTab() {
  const { conversations, loading, error, add, remove, deleteOne, refresh, markSeen, replaceOne } = useConversations()

  // 목록에서 밀어서 「종료」(할 일·일정은 뽑지 않음, 대화방에서 나중에 뽑을 수 있음) · 「삭제」(종료하고 바로 내 목록에서 지움)
  const endFromList = async (id: number, alsoDelete: boolean) => {
    setNotice(null)
    try {
      replaceOne(await closeConversation(id, false))
      if (alsoDelete) await deleteOne(id)
      setNotice(alsoDelete ? '대화를 종료하고 삭제했습니다.' : '대화를 종료했습니다. 종료된 대화에서 볼 수 있어요.')
    } catch (e) {
      setNotice(e instanceof Error ? e.message : '처리하지 못했습니다')
    }
  }
  const location = useLocation()
  const navigate = useNavigate()
  // 열린 대화는 주소(?chat=번호)에 둔다: 브라우저 뒤로 가기로 대화 목록에 돌아오고, 학생 탭에서 대화를 눌러 와도 같은 방식으로 열린다.
  const [params] = useSearchParams()
  const selectedId = Number(params.get('chat')) || null
  // 대화방에서 목록으로: 목록에서 눌러 들어왔으면 기록을 한 칸 되돌리고(뒤로 가기와 같음), 아니면(학생 탭에서 왔거나 주소로 바로 들어옴) 이 기록을 목록으로 바꾼다
  const closeThread = () => {
    if ((location.state as { fromList?: boolean } | null)?.fromList) navigate(-1)
    else navigate('.', { replace: true })
  }
  const [starting, setStarting] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const { show, setShow, shown, openCount, closedCount, sortControl } = useStatusFilter(conversations) // 대화 중 / 종료된 대화
  const selected = conversations.find((c) => c.id === selectedId) ?? null
  const todoCount = useOpenTodoCount()

  // 403·404 를 받으면 안내를 남기고 목록으로 돌아온다 (명세 3.1)
  const leave = (message: string) => {
    setNotice(message)
    navigate('.', { replace: true })
  }
  const select = (id: number) => {
    markSeen(id)
    setNotice(null)
    navigate({ search: `?chat=${id}` }, { state: { fromList: true } })
  }

  const newButton = (
    <button
      type="button"
      className="new-conv"
      onClick={() => setStarting((v) => !v)}
      aria-expanded={starting}
    >
      {starting ? '닫기' : '＋ 새 대화'}
    </button>
  )

  if (selected) {
    return (
      <TeacherThread
        key={selected.id}
        conversation={selected}
        onLeave={leave}
        onBack={() => {
          closeThread()
          void refresh() // 보는 동안 읽은 것을 목록 숫자에 반영
        }}
        onDeleted={(id) => {
          remove(id)
          closeThread()
          setNotice('대화를 삭제했습니다.')
        }}
      />
    )
  }

  return (
    <section>
      <TeacherDashboard
        unreadCount={conversations.filter((c) => c.status === 'open' && c.unread).length}
        todoCount={todoCount}
        onOpenConversations={() => setShow('open')}
      />
      {loading && <p className="loading">불러오는 중</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      {notice && <p className="alert" role="alert" ref={revealRef}>{notice}</p>}
      {!loading && !error && conversations.length === 0 && (
        <div className="empty">
          <div className="big">▤</div>아직 대화가 없어요. 「＋ 새 대화」로 학부모와 대화를 시작하세요
        </div>
      )}
      {conversations.length > 0 ? (
        <StatusFilter show={show} setShow={setShow} openCount={openCount} closedCount={closedCount}
          shownCount={shown.length}
          sort={sortControl}
          extra={newButton} />
      ) : (
        <div className="filter-row">{newButton}</div>
      )}
      {starting && (
        <StartConversation
          role="teacher"
          onCancel={() => setStarting(false)}
          onStarted={(c) => {
            add(c)
            setStarting(false)
            setShow('open')
            select(c.id)
          }}
        />
      )}
      <ConversationList
        conversations={shown}
        onSelect={select}
        onEnd={(id, alsoDelete) => void endFromList(id, alsoDelete)}
        onDelete={(id) =>
          void deleteOne(id).then(
            () => setNotice('대화를 삭제했습니다.'),
            (e: unknown) => setNotice(e instanceof Error ? e.message : '삭제하지 못했습니다'),
          )
        }
      />
    </section>
  )
}
