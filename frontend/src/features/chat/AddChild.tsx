import { useState, type FormEvent } from 'react'
import { addChild } from '../../api/students'
import type { Startable } from '../../api/types'

// 학부모: 초대 코드로 자녀 더하기 (자녀가 여럿이면 각 담임의 코드로 하나씩). 성공하면 onAdded 로 새 줄을 돌려준다.
export default function AddChild({ onAdded }: { onAdded: (s: Startable) => void }) {
  const [open, setOpen] = useState(false)
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (!open) {
    return (
      <button type="button" className="outline" onClick={() => setOpen(true)}>
        ＋ 초대 코드로 자녀 추가
      </button>
    )
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (busy) return
    if (code.trim() === '' || name.trim() === '') {
      setError('초대 코드와 자녀 이름을 적어 주세요')
      return
    }
    setBusy(true)
    setError(null)
    try {
      onAdded(await addChild(code.trim(), name.trim()))
      setCode('')
      setName('')
      setOpen(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : '추가하지 못했습니다')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="manual-form add-child" onSubmit={onSubmit} noValidate>
      <label className="editor-label" htmlFor="child-code">담임 선생님 초대 코드</label>
      <input
        id="child-code"
        className="invite-input"
        value={code}
        onChange={(e) => setCode(e.target.value.toUpperCase())}
        autoComplete="off"
        autoCapitalize="characters"
        spellCheck={false}
      />
      <label className="editor-label" htmlFor="child-name">자녀 이름</label>
      <input id="child-name" value={name} onChange={(e) => setName(e.target.value)} autoComplete="off" />
      {error && <p className="alert" role="alert">{error}</p>}
      <div className="form-actions">
        <button type="button" className="outline" onClick={() => setOpen(false)} disabled={busy}>
          취소
        </button>
        <button type="submit" className="primary" disabled={busy}>
          {busy ? '추가하는 중' : '자녀 추가'}
        </button>
      </div>
    </form>
  )
}
