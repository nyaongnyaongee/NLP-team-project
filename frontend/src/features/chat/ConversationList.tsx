import { useState } from 'react'
import type { Conversation } from '../../api/types'
import SwipeRow, { type SwipeAction } from './SwipeRow'
import { formatTime } from './formatTime'

const lastAt = (c: Conversation) => c.last_message_at ?? c.created_at

// 마지막 글 한 줄. 교사에게 내용이 없는 글(정제 전 · 실패)은 상태로 문구를 고른다.
function lastLine(c: Conversation): string | null {
  if (!c.preview) return null // 예전 서버
  const last = c.preview.last
  if (!last) return '아직 메시지가 없습니다'
  const who = last.mine ? '나: ' : ''
  if (last.text !== null) return who + last.text
  if (last.status === 'pending') return '새 메시지를 정리하고 있습니다…'
  return '정리하지 못한 메시지가 있습니다 — 열어서 다시 정제해 주세요'
}

// 대화 목록 (교사·학부모 공용). 최근에 메시지가 오간 대화가 위. 같은 학생의 대화가 여럿이어도 시각으로 구분된다.
// 목록은 학생 이름으로 표시한다 (중대 3). 이름 옆에 대화 상태, 그 아래 요약 · 마지막 글 (교사 · 학부모 같음). 주제는 요약과 겹쳐서 안 보인다.
// 왼쪽으로 밀면 나오는 버튼:
//  - 종료된 대화: 「삭제」 (onDelete — 내 목록에서만, DB 에는 남음)
//  - 대화 중 (onEnd 를 준 교사만): 「종료」 · 「삭제」 (onEnd(id, false) = 종료만, onEnd(id, true) = 종료하고 바로 삭제)
export default function ConversationList({
  conversations,
  onSelect,
  onDelete,
  onEnd,
}: {
  conversations: Conversation[]
  onSelect: (id: number) => void
  onDelete?: (id: number) => void
  onEnd?: (id: number, alsoDelete: boolean) => void
}) {
  const [openId, setOpenId] = useState<number | null>(null) // 밀어서 삭제 버튼이 보이는 줄 (한 번에 하나)
  const sorted = [...conversations].sort((a, b) => lastAt(b).localeCompare(lastAt(a)) || b.id - a.id)
  const renderRow = (c: Conversation) => (
    <button type="button" className="row" onClick={() => onSelect(c.id)}>
      <span className="avatar">{c.student_name.slice(0, 1)}</span>
      <span className="row-main">
        <span className="row-title">
          <span className="row-name">
            <b>{c.student_name}</b>
            {c.unread ? (
              <span className="unread" aria-label={`안 읽은 메시지 ${c.unread}개`}>
                {c.unread > 99 ? '99+' : c.unread}
              </span>
            ) : null}
            <span className="tag">{c.status === 'closed' ? '대화 종료' : '대화 중'}</span>
          </span>
          <small>{c.last_message_at ? formatTime(c.last_message_at) : `시작 ${formatTime(c.created_at)}`}</small>
        </span>
        {c.preview?.summary ? (
          <span className="row-summary">{c.preview.summary}</span>
        ) : c.preview?.requests?.length ? (
          <span className="row-summary">요청 · {c.preview.requests.join(' / ')}</span>
        ) : null}
        {lastLine(c) !== null && <span className="row-last">{lastLine(c)}</span>}
      </span>
      <span className="muted" aria-hidden="true">
        ›
      </span>
    </button>
  )
  // 누르면 한 번 더 묻는다. 「아니요」면 버튼은 열린 채로 둔다
  const act = (question: string, fn: () => void) => () => {
    if (!window.confirm(question)) return
    setOpenId(null)
    fn()
  }
  const swipeActions = (c: Conversation): SwipeAction[] => {
    if (c.status === 'closed') {
      return onDelete
        ? [{ label: '삭제', ariaLabel: `${c.student_name} 대화 삭제`, danger: true, onClick: act(`${c.student_name} 대화를 삭제할까요?`, () => onDelete(c.id)) }]
        : []
    }
    return onEnd
      ? [
          { label: '종료', ariaLabel: `${c.student_name} 대화 종료`, onClick: act(`${c.student_name} 대화를 종료할까요?`, () => onEnd(c.id, false)) },
          { label: '삭제', ariaLabel: `${c.student_name} 대화 종료하고 삭제`, danger: true, onClick: act(`${c.student_name} 대화를 종료하고 삭제할까요?`, () => onEnd(c.id, true)) },
        ]
      : []
  }
  return (
    <ul className="plain-list">
      {sorted.map((c) => (
        <li key={c.id}>
          {swipeActions(c).length > 0 ? (
            <SwipeRow
              open={openId === c.id}
              onOpenChange={(o) => setOpenId(o ? c.id : null)}
              actions={swipeActions(c)}
            >
              {renderRow(c)}
            </SwipeRow>
          ) : (
            renderRow(c)
          )}
        </li>
      ))}
    </ul>
  )
}
