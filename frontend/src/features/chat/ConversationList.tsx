import type { Conversation } from '../../api/types'
import { formatTime } from './formatTime'

const lastAt = (c: Conversation) => c.last_message_at ?? c.created_at

// 대화 목록 (교사·학부모 공용). 최근에 메시지가 오간 대화가 위. 같은 학생의 대화가 여럿이어도 시각으로 구분된다.
// 목록은 학생 이름으로 표시한다 (중대 3).
export default function ConversationList({
  conversations,
  onSelect,
}: {
  conversations: Conversation[]
  onSelect: (id: number) => void
}) {
  const sorted = [...conversations].sort((a, b) => lastAt(b).localeCompare(lastAt(a)) || b.id - a.id)
  return (
    <ul className="plain-list">
      {sorted.map((c) => (
        <li key={c.id}>
          <button type="button" className="row" onClick={() => onSelect(c.id)}>
            <span className="avatar">{c.student_name.slice(0, 1)}</span>
            <span className="row-main">
              <span className="row-title">
                <b>{c.student_name}</b>
                <small>{c.last_message_at ? formatTime(c.last_message_at) : `시작 ${formatTime(c.created_at)}`}</small>
              </span>
              <span className="tag">{c.status === 'closed' ? '대화 종료' : '대화 중'}</span>
            </span>
            <span className="muted" aria-hidden="true">
              ›
            </span>
          </button>
        </li>
      ))}
    </ul>
  )
}
