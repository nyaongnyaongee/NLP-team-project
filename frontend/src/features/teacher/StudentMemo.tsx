import type { StudentMemoState } from './useStudentMemo'

const MAX = 20000 // 서버 MemoIn.body 최대 길이

// 이름 옆 작은 알약 「✎ 메모」.
export function MemoToggle({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  return (
    <button type="button" className={`memo-toggle${open ? ' on' : ''}`} onClick={onToggle} aria-expanded={open}>
      ✎ 메모
    </button>
  )
}

// 메모 칸
export function MemoPanel({ memo, studentName }: { memo: StudentMemoState; studentName: string }) {
  if (memo.loadError) return <p className="alert" role="alert">{memo.loadError}</p>
  return (
    <div className="memo-panel">
      <textarea
        aria-label={`${studentName} 학생 메모`}
        value={memo.text}
        maxLength={MAX}
        disabled={!memo.loaded}
        placeholder={memo.loaded ? '예: 큰 소리에 놀람 — 활동 전에 미리 알려 주면 괜찮음' : '불러오는 중'}
        onChange={(e) => memo.change(e.target.value)}
        onBlur={() => void memo.save()}
      />
      <p className="info">
        나만 보는 메모예요. 학부모에게도, AI 에게도 가지 않아요.
        <span className="memo-state" aria-live="polite">
          {memo.state === 'saving' && ' 저장 중…'}
          {memo.state === 'saved' && ' 저장됨'}
          {memo.state === 'error' && ' 저장 실패'}
        </span>
      </p>
      {memo.state === 'error' && (
        <button type="button" className="outline" onClick={() => void memo.save()}>
          다시 저장
        </button>
      )}
    </div>
  )
}
