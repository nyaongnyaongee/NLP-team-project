import { useState } from 'react'
import { makeNoticeDraft } from '../../api/drafts'
import DraftChecks from '../drafts/DraftChecks'
import { useDraftRequest } from '../drafts/useDraftRequest'

const POINTS_MAX = 2000 // 명세 8장 (서버: 1~2000자)
const countChars = (s: string) => [...s].length

// 공지 작성의 "AI 초안": 전달할 내용(주제)을 적으면 제목과 본문을 채운다. 자동으로 저장하거나 게시하지 않는다.
export default function NoticeDraftPanel({
  getCurrent,
  onFill,
}: {
  getCurrent: () => { title: string; body: string }
  onFill: (title: string, body: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [points, setPoints] = useState('')
  const [checks, setChecks] = useState<string[] | null>(null)
  const [previous, setPrevious] = useState<{ title: string; body: string } | null>(null)
  const { pending, error, run } = useDraftRequest()
  const len = countChars(points)
  const tooLong = len > POINTS_MAX
  const empty = points.trim() === ''

  async function onMake() {
    if (tooLong || empty) return
    const result = await run(() => makeNoticeDraft(points.trim()))
    if (!result) return
    const before = getCurrent()
    setPrevious(before.title.trim() === '' && before.body.trim() === '' ? null : before) // 쓰던 글을 잃지 않게
    onFill(result.title, result.body)
    setChecks(result.check)
  }

  function onRestore() {
    if (previous) onFill(previous.title, previous.body)
    setPrevious(null)
  }

  return (
    <div>
      <button type="button" className="outline" onClick={() => setOpen((o) => !o)} aria-expanded={open} disabled={pending}>
        AI 초안
      </button>
      {open && (
        <div className="notice-draft-composer">
          <label htmlFor="notice-points">공지에 담을 내용</label>
          <textarea id="notice-points" value={points} onChange={(e) => setPoints(e.target.value)} rows={4} disabled={pending} />
          <div className={`char ${tooLong ? 'over' : ''}`}>
            {len}/{POINTS_MAX}
          </div>
          {tooLong && <p className="alert" role="alert">내용은 {POINTS_MAX}자까지 쓸 수 있어요</p>}
          <button
            type="button"
            className="notice-draft-button"
            onClick={() => void onMake()}
            disabled={pending || tooLong || empty}
          >
            {pending ? (<><span className="spinner blue" />초안 작성 중</>) : error ? '다시 시도' : '초안 만들기'}
          </button>
          {pending && <p className="notice-draft-status" role="status">초안 작성 중… 몇 초 걸려요</p>}
          {error && <p className="alert" role="alert">{error}</p>}
        </div>
      )}
      {checks && (
        <DraftChecks items={checks}>
          {/* 공지는 반 학생의 학부모 모두에게 간다 (서버 crud.notice_recipients) */}
          <p>
            <strong>이 공지는 반 학부모 모두에게 보내져요.</strong> 학생 이름이나 개인 사정이 들어 있으면 모두에게 해당하는
            공통 안내로 고쳐 주세요.
          </p>
        </DraftChecks>
      )}
      {previous && (
        <button type="button" className="notice-draft-restore" onClick={onRestore}>
          초안 대신 이전에 쓰던 글로 되돌리기
        </button>
      )}
    </div>
  )
}
