import { useState, type RefObject } from 'react'
import { makeReplyDraft } from '../../api/drafts'
import type { MessageFormHandle } from '../chat/MessageForm'
import DraftChecks from '../drafts/DraftChecks'
import { useDraftRequest } from '../drafts/useDraftRequest'

const MEMO_MAX = 1000 // 명세 8장

// 글자 수는 서버(파이썬)와 같게 유니코드 글자 단위로 센다.
const countChars = (s: string) => [...s].length

// 교사 대화방의 "답장 초안": 메모(선택)를 적으면 AI 초안을 답장 입력창에 채운다. 자동으로 보내지 않는다.
// 서버는 초안을 저장하지 않는다 (S7 만들지 않을 것).
export default function ReplyDraftPanel({
  conversationId,
  formRef,
}: {
  conversationId: number
  formRef: RefObject<MessageFormHandle | null>
}) {
  const [open, setOpen] = useState(false)
  const [memo, setMemo] = useState('')
  const [checks, setChecks] = useState<string[] | null>(null)
  const [previous, setPrevious] = useState<string | null>(null) // 초안이 덮어쓴 입력 (되돌리기용)
  const { pending, error, run } = useDraftRequest()
  const memoLen = countChars(memo)
  const tooLong = memoLen > MEMO_MAX

  async function onMake() {
    if (tooLong) return
    const result = await run(() => makeReplyDraft(conversationId, memo.trim() || undefined))
    if (!result) return
    const before = formRef.current?.getText() ?? ''
    setPrevious(before.trim() === '' ? null : before) // 쓰던 글이 있었다면 잃지 않게 되돌릴 수 있다
    formRef.current?.setText(result.draft) // 입력창에 채울 뿐, 보내지 않는다
    setChecks(result.check)
  }

  function onRestore() {
    if (previous !== null) formRef.current?.setText(previous)
    setPrevious(null)
  }

  return (
    <div>
      <button type="button" className="outline" onClick={() => setOpen((o) => !o)} aria-expanded={open} disabled={pending}>
        답장 초안
      </button>
      {open && (
        <div className="notice-draft-composer">
          <label htmlFor="draft-memo">이번 답장에 담고 싶은 내용 (선택)</label>
          <textarea id="draft-memo" value={memo} onChange={(e) => setMemo(e.target.value)} rows={3} disabled={pending} />
          <div className={`char ${tooLong ? 'over' : ''}`}>
            {memoLen}/{MEMO_MAX}
          </div>
          {tooLong && <p className="alert" role="alert">메모는 {MEMO_MAX}자까지 쓸 수 있어요</p>}
          <button type="button" className="notice-draft-button" onClick={() => void onMake()} disabled={pending || tooLong}>
            {pending ? (<><span className="spinner blue" />초안 작성 중</>) : error ? '다시 시도' : '초안 만들기'}
          </button>
          {pending && <p className="notice-draft-status" role="status">초안 작성 중… 몇 초 걸려요</p>}
          {error && <p className="alert" role="alert">{error}</p>}
        </div>
      )}
      {checks && <DraftChecks items={checks} />}
      {previous !== null && (
        <button type="button" className="notice-draft-restore" onClick={onRestore}>
          초안 대신 이전에 쓰던 글로 되돌리기
        </button>
      )}
    </div>
  )
}
