import { useState } from 'react'
import type { Conversation } from '../../api/types'
import SwipeRow, { type SwipeAction } from './SwipeRow'
import { formatTime } from './formatTime'
import { parentLabel, parentTitle, teacherTitle } from './chatTitle'

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

// 대화 목록 (교사·학부모 공용). 받은 순서대로 그린다 — 정렬은 부르는 쪽이 한다 (useStatusFilter · sortConversations). 같은 학생의 대화가 여럿이어도 시각으로 구분된다.
// 목록은 대화 상대로 표시한다 (교사 화면 「박서연 (박지민의 학부모)」, 학부모 화면 「김민지 선생님」). 이름 아래 요약 · 마지막 글 (교사 · 학부모 같음). 진행 중 / 종료는 목록 위 탭이 나누므로 줄에는 표시하지 않는다.
// 왼쪽으로 밀거나(스와이프) 마우스를 올렸을 때 나오는 「⋯」 를 누르면 줄이 밀리며 오른쪽에 동작 버튼이 나온다 (SwipeRow, 같은 동작):
//  - 종료된 대화: 「삭제」 (onDelete — 내 목록에서만, DB 에는 남음)
//  - 진행 중인 대화 (onEnd 를 준 화면만 — 교사 · 학부모): 「종료」 · 「삭제」 (onEnd(id, false) = 종료만, onEnd(id, true) = 종료하고 바로 삭제)
//  버튼은 두 번 눌러 실행한다 (처음 누르면 「다시 눌러 확인」).
export default function ConversationList({
  conversations,
  onSelect,
  onDelete,
  onEnd,
  showTeacher = false,
}: {
  showTeacher?: boolean // 학부모 화면: 「○○○ 선생님」, 교사 화면(기본): 「○○○ (○○○의 학부모)」
  conversations: Conversation[]
  onSelect: (id: number) => void
  onDelete?: (id: number) => void
  onEnd?: (id: number, alsoDelete: boolean) => void
}) {
  const [openId, setOpenId] = useState<number | null>(null) // 동작 버튼이 열린 줄 (한 번에 하나)
  const titleOf = (c: Conversation) => (showTeacher ? teacherTitle(c) : parentTitle(c))

  // 줄은 카드(div) 하나 안에 「대화 열기」 버튼이 있고, 동작이 있는 줄이면 ⋯(마우스 호버 시) · ✕(열린 동안)가 › 자리에 겹쳐 있다.
  // 그래서 이 버튼들은 글 자리를 차지하지 않는다.
  const renderRow = (c: Conversation, menu?: { open: boolean; requestOpen: () => void; requestClose: () => void }) => (
    <div className="row row-card">
      <button type="button" className="row-open" onClick={() => onSelect(c.id)}>
        <span className="avatar-wrap">
          <span className="avatar">{titleOf(c).slice(0, 1)}</span>
          {c.unread ? (
            <span className="unread on-avatar" aria-label={`안 읽은 메시지 ${c.unread}개`}>
              {c.unread > 99 ? '99+' : c.unread}
            </span>
          ) : null}
        </span>
        <span className="row-main">
          <span className="row-title">
            <span className="row-name">
              {showTeacher ? (
                <b>{titleOf(c)}</b>
              ) : (
                <>
                  <b>{parentLabel(c).name}</b>
                  {parentLabel(c).sub && <span className="row-sub">{parentLabel(c).sub}</span>}
                </>
              )}
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
        <span className="muted row-chevron" aria-hidden="true">
          ›
        </span>
      </button>
      {menu && !menu.open && (
        <button
          type="button"
          className="row-toggle row-more"
          data-swipe-toggle
          aria-label={`${titleOf(c)} 대화 관리`}
          aria-expanded={false}
          onClick={menu.requestOpen}
        >
          ⋯
        </button>
      )}
      {menu?.open && (
        <button
          type="button"
          className="row-toggle row-close"
          data-swipe-toggle
          aria-label={`${titleOf(c)} 대화 관리 닫기`}
          aria-expanded
          onClick={menu.requestClose}
        >
          ✕
        </button>
      )}
    </div>
  )

  const actionsOf = (c: Conversation): SwipeAction[] => {
    const t = titleOf(c)
    if (c.status === 'closed') {
      return onDelete
        ? [{ key: 'delete', label: '삭제', ariaLabel: `${t} 대화 삭제`, danger: true, onConfirm: () => onDelete(c.id) }]
        : []
    }
    return onEnd
      ? [
          { key: 'end', label: '종료', ariaLabel: `${t} 대화 종료`, onConfirm: () => onEnd(c.id, false) },
          { key: 'delete', label: '삭제', ariaLabel: `${t} 대화 종료하고 삭제`, danger: true, onConfirm: () => onEnd(c.id, true) },
        ]
      : []
  }

  return (
    <ul className="plain-list conv-list">
      {conversations.map((c) => {
        const actions = actionsOf(c)
        const open = openId === c.id
        return (
          <li key={c.id}>
            {actions.length > 0 ? (
              <SwipeRow open={open} onOpenChange={(o) => setOpenId(o ? c.id : null)} actions={actions}>
                {({ requestOpen, requestClose }) => renderRow(c, { open, requestOpen, requestClose })}
              </SwipeRow>
            ) : (
              renderRow(c)
            )}
          </li>
        )
      })}
    </ul>
  )
}
