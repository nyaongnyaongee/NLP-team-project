import { useEffect, useMemo, useState } from 'react'
import { listConversations } from '../../api/conversations'
import { listMessages } from '../../api/messages'
import type { Conversation, Message } from '../../api/types'
import { parentLabel } from '../chat/chatTitle'
import { formatTime } from '../chat/formatTime'
import { teacherView } from '../chat/messageText'

const SHOW = 5 // 처음엔 최근 5개만, 「더 보기」로 전부

const lastAt = (c: Conversation) => c.last_message_at ?? c.created_at

// Q&A · 공지를 쓸 때 바탕으로 삼을 대화 고르기 (공지사항 탭).
// 대화 카드(학부모 · 날짜 · 요약 · 마지막 글)를 누르면 그 자리에서 대화 내용이 펼쳐지고, 읽어 본 뒤 「이 대화로 쓰기」.
// 고른 뒤에는 카드 한 장으로 접히고, 「대화 보기」로 다시 펼쳐 볼 수 있다. 내용은 교사 대화창과 같은 규칙(teacherView)으로 보인다.
export default function ChatSourcePicker({
  value,
  onChange,
  disabled = false,
}: {
  value: number | null
  onChange: (id: number | null) => void
  disabled?: boolean
}) {
  const [convs, setConvs] = useState<Conversation[] | null>(null)
  const [listError, setListError] = useState<string | null>(null)
  const [open, setOpen] = useState(false) // 목록 펼침
  const [all, setAll] = useState(false)
  const [query, setQuery] = useState('')
  const [viewId, setViewId] = useState<number | null>(null) // 내용을 펼친 대화

  useEffect(() => {
    let alive = true
    listConversations()
      .then((rows) => {
        if (alive) setConvs(rows.filter((c) => c.last_message_at).sort((a, b) => lastAt(b).localeCompare(lastAt(a))))
      })
      .catch((e) => alive && setListError(e instanceof Error ? e.message : '대화 목록을 불러오지 못했습니다'))
    return () => {
      alive = false
    }
  }, [])

  const filtered = useMemo(() => {
    const q = query.trim()
    if (!convs) return []
    if (q === '') return convs
    return convs.filter((c) =>
      [c.parent_name, c.student_name, c.preview?.summary, c.preview?.last?.text].some((s) => s?.includes(q)),
    )
  }, [convs, query])
  const shown = all || query.trim() !== '' ? filtered : filtered.slice(0, SHOW)
  const picked = convs?.find((c) => c.id === value) ?? null

  function pick(id: number) {
    onChange(id)
    setOpen(false)
    setViewId(null)
  }

  if (listError) return <p className="alert" role="alert">{listError}</p>
  if (convs === null) return <p className="loading">대화 불러오는 중</p>
  if (convs.length === 0) return null

  // 고른 대화: 카드 한 장 + 대화 보기 · 바꾸기 · 빼기
  if (picked && !open) {
    const showing = viewId === picked.id
    return (
      <div className="src-picked">
        <ConvCard c={picked} />
        <div className="src-picked-actions">
          <button type="button" className="link-button" onClick={() => setViewId(showing ? null : picked.id)}>
            {showing ? '대화 접기' : '대화 보기'}
          </button>
          <button type="button" className="link-button" onClick={() => setOpen(true)} disabled={disabled}>
            다른 대화
          </button>
          <button type="button" className="link-button" onClick={() => onChange(null)} disabled={disabled}>
            빼기
          </button>
        </div>
        {showing && <ChatPreview conversation={picked} />}
      </div>
    )
  }

  if (!open) {
    return (
      <button type="button" className="outline src-open" onClick={() => setOpen(true)} disabled={disabled}>
        💬 대화에서 가져오기
      </button>
    )
  }

  return (
    <div className="src-list">
      <div className="src-list-head">
        <b>어느 대화를 볼까요?</b>
        <button type="button" className="link-button" onClick={() => setOpen(false)}>
          닫기
        </button>
      </div>
      {convs.length > SHOW && (
        <input
          className="notice-input src-search"
          type="search"
          placeholder="학부모 · 학생 이름이나 내용으로 찾기"
          aria-label="대화 찾기"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      )}
      {shown.length === 0 && <div className="empty">맞는 대화가 없어요</div>}
      {shown.map((c) => {
        const viewing = viewId === c.id
        return (
          <div key={c.id} className={`src-item${viewing ? ' on' : ''}`}>
            <button
              type="button"
              className="src-card-button"
              aria-expanded={viewing}
              onClick={() => setViewId(viewing ? null : c.id)}
            >
              <ConvCard c={c} />
              <span className="src-chevron" aria-hidden>
                {viewing ? '⌃' : '⌄'}
              </span>
            </button>
            {viewing && (
              <>
                <ChatPreview conversation={c} />
                <button type="button" className="primary src-use" onClick={() => pick(c.id)}>
                  이 대화로 쓰기
                </button>
              </>
            )}
          </div>
        )
      })}
      {!all && query.trim() === '' && filtered.length > SHOW && (
        <button type="button" className="link-button src-more" onClick={() => setAll(true)}>
          대화 {filtered.length - SHOW}개 더 보기
        </button>
      )}
    </div>
  )
}

function ConvCard({ c }: { c: Conversation }) {
  const label = parentLabel(c)
  const last = c.preview?.last
  return (
    <span className="src-card">
      <span className="src-card-top">
        <b>{label.name}</b>
        {label.sub && <small>{label.sub}</small>}
        <time>{formatTime(lastAt(c))}</time>
      </span>
      {c.preview?.summary && <span className="src-summary">{c.preview.summary}</span>}
      {last?.text && (
        <span className="src-last">
          {last.mine ? '나: ' : ''}
          {last.text}
        </span>
      )}
      {c.status === 'closed' && <span className="tag">종료</span>}
    </span>
  )
}

// 대화 내용 (읽기 전용). 읽음 처리는 하지 않는다 (목록에서 메시지만 가져옴).
function ChatPreview({ conversation }: { conversation: Conversation }) {
  const [messages, setMessages] = useState<Message[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    listMessages(conversation.id)
      .then((rows) => alive && setMessages(rows))
      .catch((e) => alive && setError(e instanceof Error ? e.message : '대화를 불러오지 못했습니다'))
    return () => {
      alive = false
    }
  }, [conversation.id])

  if (error) return <p className="alert" role="alert">{error}</p>
  if (messages === null) return <p className="loading">대화 불러오는 중</p>
  return (
    <ul className="chat-log src-chat" aria-label="대화 내용">
      {messages.map((m) => {
        const mine = m.sender_id === conversation.teacher_id
        const view = teacherView(m)
        const text =
          view.kind === 'text'
            ? view.text
            : view.kind === 'pending'
              ? '정리 중인 메시지'
              : view.kind === 'failed'
                ? '정리하지 못한 메시지 (대화창에서 다시 정제)'
                : '표시할 수 있는 내용이 없습니다'
        return (
          <li key={m.id} className={`chat-message ${mine ? 'mine' : ''}`}>
            <div className="chat-name">
              {mine ? '나' : parentLabel(conversation).name} <span>{formatTime(m.created_at)}</span>
            </div>
            <div className={`chat-bubble${view.kind === 'text' ? '' : ' muted'}`}>{text}</div>
          </li>
        )
      })}
    </ul>
  )
}
