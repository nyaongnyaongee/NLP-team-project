import { useEffect, useRef, useState, type FormEvent } from 'react'
import { createFaq, makeFaqDraft, updateFaq } from '../../api/faqs'
import type { Faq } from '../../api/types'
import DraftChecks from '../drafts/DraftChecks'
import { useDraftRequest } from '../drafts/useDraftRequest'

const MEMO_MAX = 1000
const Q_MAX = 200
const A_MAX = 3000
const len = (s: string) => [...s].length // 서버(파이썬)와 같게 글자 단위

// Q&A 쓰기 · 고치기. 새로 쓸 때는 위에 「메모 → AI 로 정리」 칸이 있다.
// 대화창에서 열면(conversationId) 메모 없이 바로 그 대화를 보고 초안을 만든다. 메모는 다시 만들 때 방향을 주는 선택 칸.
// AI 결과는 질문 · 답변 칸에 채워질 뿐이고, 교사가 읽고 [등록] 해야 학부모에게 보인다.
export default function FaqEditor({
  faq = null,
  conversationId,
  onSaved,
  onCancel,
}: {
  faq?: Faq | null
  conversationId?: number
  onSaved: (f: Faq) => void
  onCancel: () => void
}) {
  const [memo, setMemo] = useState('')
  const [question, setQuestion] = useState(faq?.question ?? '')
  const [answer, setAnswer] = useState(faq?.answer ?? '')
  const [checks, setChecks] = useState<string[] | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const draft = useDraftRequest()

  const fromChat = conversationId != null && !faq
  const memoTooLong = len(memo) > MEMO_MAX
  const canMake = !memoTooLong && (fromChat || memo.trim() !== '')
  const problem =
    question.trim() === '' || answer.trim() === ''
      ? '질문과 답변을 모두 적어 주세요'
      : len(question) > Q_MAX
        ? `질문은 ${Q_MAX}자까지 쓸 수 있어요`
        : len(answer) > A_MAX
          ? `답변은 ${A_MAX}자까지 쓸 수 있어요`
          : null

  async function onMake() {
    if (!canMake) return
    const result = await draft.run(() => makeFaqDraft(memo.trim(), conversationId))
    if (!result) return
    setQuestion(result.question)
    setAnswer(result.answer)
    setChecks(result.check)
  }

  // 대화창에서 열면 바로 한 번 만든다 (교사가 내용을 적지 않아도 되게)
  const autoRef = useRef(false)
  useEffect(() => {
    if (!fromChat || autoRef.current) return
    autoRef.current = true
    void onMake()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (problem || saving) return
    setSaving(true)
    setError(null)
    try {
      const body = { question: question.trim(), answer: answer.trim() }
      onSaved(faq ? await updateFaq(faq.id, body) : await createFaq(body))
    } catch (err) {
      setError(err instanceof Error ? err.message : '저장하지 못했습니다')
      setSaving(false)
    }
  }

  const touched = question !== '' || answer !== ''
  return (
    <form className="faq-editor" onSubmit={onSubmit}>
      {!faq && (
        <div className="faq-memo">
          <label className="editor-label" htmlFor="faq-memo">
            {fromChat ? '꼭 담을 내용 (선택)' : '어떤 내용을 Q&A 로 남길까요?'}
          </label>
          <textarea
            id="faq-memo"
            className="notice-input"
            rows={fromChat ? 1 : 2}
            placeholder={fromChat ? '비워 두면 대화를 보고 알아서 써요' : '예) 체험학습 신청서는 3일 전까지, 양식은 학교 홈페이지'}
            value={memo}
            onChange={(e) => setMemo(e.target.value)}
            disabled={draft.pending}
          />
          <button
            type="button"
            className="outline faq-make"
            onClick={() => void onMake()}
            disabled={draft.pending || !canMake}
          >
            {draft.pending ? (
              <><span className="spinner blue" />{fromChat ? '대화를 읽고 쓰는 중…' : '정리하는 중…'}</>
            ) : fromChat ? (
              checks || draft.error ? '✦ 다시 만들기' : '✦ 대화 보고 만들기'
            ) : (
              '✦ AI 로 질문 · 답변 만들기'
            )}
          </button>
          {memoTooLong && <p className="alert" role="alert">메모는 {MEMO_MAX}자까지 쓸 수 있어요</p>}
          {draft.error && <p className="alert" role="alert">{draft.error}</p>}
        </div>
      )}

      <div className="faq-edit-pair">
        <label className="editor-label" htmlFor="faqQ">질문</label>
        <textarea
          id="faqQ"
          className="notice-input"
          rows={2}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="학부모님이 묻는 말로 (예: 체험학습 신청서는 언제까지 내나요?)"
        />
        <label className="editor-label" htmlFor="faqA">답변</label>
        <textarea id="faqA" className="notice-input" value={answer} onChange={(e) => setAnswer(e.target.value)} />
      </div>
      {checks && <DraftChecks items={checks} title="등록 전에 확인하세요" />}
      <p className="sub">등록하면 반 학부모님 모두에게 바로 보여요. 학생 · 학부모 이름이 없는지 확인해 주세요.</p>
      {problem && touched && <p className="alert" role="alert">{problem}</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      <div className="faq-buttons">
        <button type="submit" className="primary" disabled={saving || problem !== null}>
          {saving ? (<><span className="spinner" />저장 중</>) : faq ? '저장' : '등록'}
        </button>
        <button type="button" className="outline" onClick={onCancel} disabled={saving}>
          취소
        </button>
      </div>
    </form>
  )
}
