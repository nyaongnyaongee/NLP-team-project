import { useRef, useState, type FormEvent } from 'react'
import { ApiError } from '../../api/client'
import { createNotice, updateNotice } from '../../api/notices'
import type { Notice } from '../../api/types'
import NoticeDraftPanel from './NoticeDraftPanel'

export const TITLE_MAX = 100 // 명세 8장
export const BODY_MAX = 5000

// 글자 수는 서버(파이썬)와 같게 유니코드 글자 단위로 센다. (이모지 같은 글자를 JS length 로 세면 2 로 나온다)
const countChars = (s: string) => [...s].length

// 공지 작성·수정 화면. notice 가 null 이면 새 공지. 제목·본문이 비었거나 글자 수를 넘으면 저장되지 않고 이유가 보인다.
export default function NoticeEditor({
  notice,
  onSaved,
  onCancel,
  onConflict,
}: {
  notice: Notice | null
  onSaved: (notice: Notice) => void
  onCancel: () => void
  // 서버가 409 를 주면(이미 게시됨 등) 호출한다. 목록을 다시 읽으면 이 화면이 읽기 전용으로 바뀌므로,
  // 안내 문장은 부모가 이어서 보여 준다.
  onConflict: (message: string) => void
}) {
  const [title, setTitle] = useState(notice?.title ?? '')
  const [body, setBody] = useState(notice?.body ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [attempted, setAttempted] = useState(false)
  const savingRef = useRef(false) // 연타로 두 번 저장되는 것을 막는다

  const titleLen = countChars(title)
  const bodyLen = countChars(body)
  const problem =
    title.trim() === ''
      ? '제목을 입력해 주세요'
      : body.trim() === ''
        ? '본문을 입력해 주세요'
        : titleLen > TITLE_MAX
          ? `제목은 ${TITLE_MAX}자까지 쓸 수 있어요`
          : bodyLen > BODY_MAX
            ? `본문은 ${BODY_MAX}자까지 쓸 수 있어요`
            : null

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (savingRef.current) return
    if (problem !== null) {
      setAttempted(true) // 비어 있는 새 공지에서 저장을 눌러도 이유를 알려 준다
      return
    }
    savingRef.current = true
    setSaving(true)
    setError(null)
    try {
      const input = { title: title.trim(), body: body.trim() }
      const saved = notice ? await updateNotice(notice.id, input) : await createNotice(input)
      onSaved(saved)
    } catch (err) {
      // 409(이미 게시됨)는 서버의 detail 문장을 그대로 보여 준다 (명세 3.1). 입력 내용은 지우지 않는다.
      const message = err instanceof Error ? err.message : '저장하지 못했습니다'
      setError(message)
      if (err instanceof ApiError && err.status === 409) onConflict(message)
    } finally {
      savingRef.current = false
      setSaving(false)
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      <button type="button" className="back" onClick={onCancel} disabled={saving}>
        ‹ 공지사항
      </button>
      <div className="eyebrow">NEW NOTICE</div>
      <h2>{notice ? '공지 수정' : '새 공지 작성'}</h2>
      {/* AI 초안은 제목·본문에 채울 뿐, 저장도 게시도 자동으로 하지 않는다 (S7) */}
      <NoticeDraftPanel
        getCurrent={() => ({ title, body })}
        onFill={(t, b) => {
          setTitle(t)
          setBody(b)
          setAttempted(false)
        }}
      />
      <label className="editor-label" htmlFor="notice-title">제목</label>
      <input
        className="notice-input"
        id="notice-title"
        value={title}
        placeholder="공지 제목을 입력하세요"
        onChange={(e) => setTitle(e.target.value)}
      />
      <div className={`char ${titleLen > TITLE_MAX ? 'over' : ''}`} aria-live="polite">
        {titleLen}/{TITLE_MAX}
      </div>
      <label className="editor-label" htmlFor="notice-body">본문</label>
      <textarea
        className="notice-body-input"
        id="notice-body"
        value={body}
        placeholder="학부모에게 전달할 내용을 입력하세요"
        onChange={(e) => setBody(e.target.value)}
        rows={8}
      />
      <div className={`char ${bodyLen > BODY_MAX ? 'over' : ''}`} aria-live="polite">
        {bodyLen}/{BODY_MAX}
      </div>
      {problem && (attempted || title !== '' || body !== '' || notice) && <p className="alert" role="alert">{problem}</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      {/* 문제가 있어도 버튼은 눌러 볼 수 있다: 저장은 되지 않고 이유가 보인다 */}
      <button type="submit" className="primary" disabled={saving} aria-disabled={problem !== null} style={{ marginTop: 18 }}>
        {saving ? (<><span className="spinner" />저장 중</>) : '저장'}
      </button>
    </form>
  )
}
