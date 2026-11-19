import { useState } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { closeConversation } from '../../api/conversations'
import ConversationList from '../chat/ConversationList'
import StartConversation from '../chat/StartConversation'
import StatusFilter from '../chat/StatusFilter'
import { useStatusFilter } from '../chat/useStatusFilter'
import { useConversations } from '../chat/useConversations'
import ParentChat from './ParentChat'

// 학부모 "대화" 탭: 대화 목록 → 대화방 (‹ 대화 목록 으로 돌아옴). 문의마다 「＋ 새 문의」로 새 대화방을 연다.
export default function ParentConversationTab() {
  const { conversations, loading, error, add, remove, deleteOne, refresh, markSeen, replaceOne } = useConversations()
  // 열린 대화는 주소(?chat=번호)에 둔다: 브라우저 뒤로 가기로 대화 목록에 돌아온다.
  const location = useLocation()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const selectedId = Number(params.get('chat')) || null
  const open = (id: number) => {
    markSeen(id)
    navigate({ search: `?chat=${id}` }, { state: { fromList: true } })
  }
  // 대화방에서 목록으로: 목록에서 눌러 들어왔으면 기록을 한 칸 되돌리고(뒤로 가기와 같음), 아니면 이 기록을 목록으로 바꾼다
  const closeThread = () => {
    if ((location.state as { fromList?: boolean } | null)?.fromList) navigate(-1)
    else navigate('.', { replace: true })
  }
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)
  const { show, setShow, shown, openCount, closedCount, sortControl } = useStatusFilter(conversations, 'parent') // 대화 중 / 종료된 대화
  const selected = conversations.find((c) => c.id === selectedId) ?? null

  if (selected) {
    return (
      <ParentChat
        key={selected.id}
        conversation={selected}
        onBack={() => {
          closeThread()
          void refresh() // 보는 동안 읽은 것을 목록 숫자에 반영
        }}
        onDeleted={(id) => {
          remove(id)
          closeThread()
        }}
      />
    )
  }

  const empty = !loading && !error && conversations.length === 0
  return (
    <section>
      <div className="eyebrow">CONVERSATIONS</div>
      <div className="notice-heading">
        <h2>선생님과의 대화</h2>
        {!starting && !empty && (
          <button type="button" className="notice-create" onClick={() => setStarting(true)}>
            ＋ 새 문의
          </button>
        )}
      </div>
      {loading && <p className="loading">불러오는 중</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      {(starting || empty) && (
        <StartConversation
          role="parent"
          onCancel={empty ? undefined : () => setStarting(false)}
          onStarted={(c) => {
            add(c)
            setStarting(false)
            setShow('open')
            open(c.id)
          }}
        />
      )}
      {empty && <p className="sub">문의할 내용마다 새 대화를 열 수 있어요</p>}
      {!empty && !loading && (
        <StatusFilter show={show} setShow={setShow} openCount={openCount} closedCount={closedCount}
          shownCount={shown.length} sort={sortControl} />
      )}
      {deleteError && <p className="alert" role="alert">{deleteError}</p>}
      <ConversationList
        showTeacher
        conversations={shown}
        onSelect={open}
        onDelete={(id) => {
          setDeleteError(null)
          void deleteOne(id).catch((e: unknown) => setDeleteError(e instanceof Error ? e.message : '삭제하지 못했습니다'))
        }}
        onEnd={(id, alsoDelete) => {
          // 밀어서 「종료」 · 「삭제」(종료하고 바로 내 목록에서 지움). 할 일·일정은 뽑지 않는다
          setDeleteError(null)
          void (async () => {
            replaceOne(await closeConversation(id, false))
            if (alsoDelete) await deleteOne(id)
          })().catch((e: unknown) => setDeleteError(e instanceof Error ? e.message : '종료하지 못했습니다'))
        }}
      />
    </section>
  )
}
