import type { ConversationStatus } from './useStatusFilter'

// 「대화 중」 / 「종료된 대화」 버튼 (교사·학부모 공용)
export default function StatusFilter({
  show,
  setShow,
  openCount,
  closedCount,
  shownCount,
  openHint,
}: {
  show: ConversationStatus
  setShow: (s: ConversationStatus) => void
  openCount: number
  closedCount: number
  shownCount: number
  openHint?: string // 「대화 중」 목록 위 안내 (교사: 밀어서 종료)
}) {
  return (
    <>
      <div className="chips" role="group" aria-label="대화 상태">
        <button
          type="button"
          className={show === 'open' ? 'active' : ''}
          aria-pressed={show === 'open'}
          onClick={() => setShow('open')}
        >
          대화 중 {openCount}
        </button>
        <button
          type="button"
          className={show === 'closed' ? 'active' : ''}
          aria-pressed={show === 'closed'}
          onClick={() => setShow('closed')}
        >
          종료된 대화 {closedCount}
        </button>
      </div>
      {show === 'open' && shownCount > 0 && openHint && <p className="info">{openHint}</p>}
      {show === 'closed' && shownCount > 0 && <p className="info">왼쪽으로 밀면 내 목록에서 삭제할 수 있어요.</p>}
      {shownCount === 0 && (
        <p className="info">{show === 'open' ? '진행 중인 대화가 없습니다.' : '종료된 대화가 없습니다.'}</p>
      )}
    </>
  )
}
