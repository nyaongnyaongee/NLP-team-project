import { useEffect, useRef, useState } from 'react'
import { makeNoticeDraft } from '../../api/drafts'
import { createNotice, sendNotice } from '../../api/notices'
import DraftChecks from '../drafts/DraftChecks'
import { useDraftRequest } from '../drafts/useDraftRequest'

const POINTS_MAX = 2000
const TITLE_MAX = 100
const BODY_MAX = 5000
const len = (s: string) => [...s].length

// 대화창에서 공지 만들기: 열자마자 그 대화를 보고 공지 초안(제목 · 본문)을 채운다. 요점은 다시 만들 때 방향을 주는 선택 칸.
// 교사가 읽고 고쳐서 [게시](반 학부모 모두에게 바로) 또는 [임시 저장](공지사항 탭에서 이어 쓰기).
export default function ChatNoticeEditor({
  conversationId,
  onDone,
  onCancel,
}: {
  conversationId: number
  onDone: (result: 'sent' | 'draft') => void
  onCancel: () => void
}) {
  const [points, setPoints] = useState('')
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [checks, setChecks] = useState<string[] | null>(null)
  const [saving, setSaving] = useState<'sent' | 'draft' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const draft = useDraftRequest()
  const createdRef = useRef<number | null>(null) // 이미 임시 저장된 공지 번호 (게시 재시도용)

  const pointsTooLong = len(points) > POINTS_MAX
  const problem =
    title.trim() === '' || body.trim() === ''
      ? '제목과 본문을 모두 적어 주세요'
      : len(title) > TITLE_MAX
        ? `제목은 ${TITLE_MAX}자까지 쓸 수 있어요`
        : len(body) > BODY_MAX
          ? `본문은 ${BODY_MAX}자까지 쓸 수 있어요`
          : null

  async function onMake() {
    if (pointsTooLong) return
    const result = await draft.run(() => makeNoticeDraft(points.trim(), conversationId))
    if (!result) return
    setTitle(result.title)
    setBody(result.body)
    setChecks(result.check)
  }

  // 열면 바로 한 번 만든다
  const autoRef = useRef(false)
  useEffect(() => {
    if (autoRef.current) return
    autoRef.current = true
    void onMake()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function onSave(kind: 'sent' | 'draft') {
    if (problem || saving) return
    setSaving(kind)
    setError(null)
    try {
      // 게시가 저장 뒤 보내기에서 실패하면, 다시 누를 때 또 만들지 않고 그 공지를 보낸다 (보내기 전 고친 내용은 공지사항 탭에서)
      const id = createdRef.current ?? (await createNotice({ title: title.trim(), body: body.trim() })).id
      createdRef.current = id
      if (kind === 'sent') await sendNotice(id)
      onDone(kind)
    } catch (e) {
      setError(e instanceof Error ? e.message : '저장하지 못했습니다')
      setSaving(null)
    }
  }

  const touched = title !== '' || body !== ''
  return (
    <div className="faq-editor">
      <div className="faq-memo">
        <label className="editor-label" htmlFor="chat-notice-points">꼭 담을 내용 (선택)</label>
        <textarea
          id="chat-notice-points"
          className="notice-input"
          rows={1}
          placeholder="비워 두면 대화를 보고 알아서 써요"
          value={points}
          onChange={(e) => setPoints(e.target.value)}
          disabled={draft.pending}
        />
        <button type="button" className="outline faq-make" onClick={() => void onMake()} disabled={draft.pending || pointsTooLong}>
          {draft.pending ? (<><span className="spinner blue" />대화를 읽고 쓰는 중…</>) : '✦ 다시 만들기'}
        </button>
        {pointsTooLong && <p className="alert" role="alert">내용은 {POINTS_MAX}자까지 쓸 수 있어요</p>}
        {draft.error && <p className="alert" role="alert">{draft.error}</p>}
      </div>

      <div className="faq-edit-pair">
        <label className="editor-label" htmlFor="chat-notice-title">제목</label>
        <input id="chat-notice-title" className="notice-input" value={title} onChange={(e) => setTitle(e.target.value)} />
        <label className="editor-label" htmlFor="chat-notice-body">본문</label>
        <textarea id="chat-notice-body" className="notice-input chat-notice-body" value={body} onChange={(e) => setBody(e.target.value)} />
      </div>
      {checks && <DraftChecks items={checks} title="게시 전에 확인하세요" />}
      <p className="sub">게시하면 반 학부모님 모두에게 바로 보내져요. 학생 · 학부모 이름이나 개인 사정이 없는지 확인해 주세요.</p>
      {problem && touched && <p className="alert" role="alert">{problem}</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      <div className="faq-buttons">
        <button type="button" className="primary" onClick={() => void onSave('sent')} disabled={saving !== null || problem !== null}>
          {saving === 'sent' ? (<><span className="spinner" />게시 중</>) : '게시'}
        </button>
        <button type="button" className="outline" onClick={() => void onSave('draft')} disabled={saving !== null || problem !== null}>
          {saving === 'draft' ? '저장 중' : '임시 저장'}
        </button>
        <button type="button" className="outline" onClick={onCancel} disabled={saving !== null}>
          취소
        </button>
      </div>
    </div>
  )
}
