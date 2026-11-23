import type { ReactNode } from 'react'
import SortSelect, { type SortControl } from './SortSelect'
import type { ConversationStatus } from './useStatusFilter'

// 「진행 중」 / 「종료」 탭 버튼 (교사·학부모 공용)
export default function StatusFilter({
  show,
  setShow,
  openCount,
  closedCount,
  shownCount,
  sort,
  extra,
}: {
  show: ConversationStatus
  setShow: (s: ConversationStatus) => void
  openCount: number
  closedCount: number
  shownCount: number
  sort?: SortControl // 정렬 셀렉트 (useStatusFilter 의 sortControl)
  extra?: ReactNode // 정렬 오른쪽에 붙는 단추 (교사 「＋ 새 대화」)
}) {
  return (
    <>
      <div className="filter-row">
      <div className="chips" role="group" aria-label="대화 상태">
        <button
          type="button"
          className={show === 'open' ? 'active' : ''}
          aria-pressed={show === 'open'}
          onClick={() => setShow('open')}
        >
          진행 중 {openCount}
        </button>
        <button
          type="button"
          className={show === 'closed' ? 'active' : ''}
          aria-pressed={show === 'closed'}
          onClick={() => setShow('closed')}
        >
          종료 {closedCount}
        </button>
      </div>
      {sort && <SortSelect control={sort} />}
      {extra}
      </div>
      {shownCount === 0 && (
        <p className="info">{show === 'open' ? '진행 중인 대화가 없습니다.' : '종료된 대화가 없습니다.'}</p>
      )}
    </>
  )
}
