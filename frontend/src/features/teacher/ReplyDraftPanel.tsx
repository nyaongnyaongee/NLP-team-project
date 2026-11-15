import { useState, type KeyboardEvent, type RefObject } from 'react'
import { makeReplyDraft } from '../../api/drafts'
import type { MessageFormHandle } from '../chat/MessageForm'
import DraftChecks from '../drafts/DraftChecks'
import { useDraftRequest } from '../drafts/useDraftRequest'

const MEMO_MAX = 1000 // 명세 8장

// 글자 수는 서버(파이썬)와 같게 유니코드 글자 단위로 센다.
const countChars = (s: string) => [...s].length

// 교사 대화방의 "답장 초안": 메모(선택)를 적으면 AI 초안을 답장 입력창에 채운다. 자동으로 보내지 않는다.
// 서버는 초안을 저장하지 않는다 (S7 만들지 않을 것).
// 열고 닫는 단추(「AI 초안」)는 입력 막대의 「답장」 옆에 있고(DraftToggle), 이 패널은 입력칸 바로 위에 들어간다.
export function DraftToggle({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      className={`draft-toggle${open ? ' on' : ''}`}
      onClick={onToggle}
      aria-expanded={open}
      aria-label="AI 답장 초안"
      title="AI 답장 초안"
    >
      ✦
    </button>
  )
}

export default function ReplyDraftPanel({
  conversationId,
  formRef,
  open,
}: {
  conversationId: number
  formRef: RefObject<MessageFormHandle | null>
  open: boolean
}) {
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

  // 메모 칸에서 Enter = 초안 만들기 (줄바꿈은 Shift+Enter)
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      void onMake()
    }
  }

  return (
    <div className="draft-panel">
      {open && (
        <div className="draft-memo">
          <div className="draft-memo-row">
            <textarea
              id="draft-memo"
              aria-label="이번 답장에 담고 싶은 내용 (선택)"
              placeholder="담고 싶은 내용 (선택)"
              value={memo}
              onChange={(e) => setMemo(e.target.value)}
              onKeyDown={onKey}
              rows={1}
              disabled={pending}
            />
            <button type="button" className="draft-make" onClick={() => void onMake()} disabled={pending || tooLong}>
              {pending ? <span className="spinner" /> : error ? '다시' : '만들기'}
            </button>
          </div>
          {pending && <p className="draft-status" role="status">초안 작성 중… 몇 초 걸려요</p>}
          {tooLong && <p className="alert" role="alert">메모는 {MEMO_MAX}자까지 쓸 수 있어요 ({memoLen}자)</p>}
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
