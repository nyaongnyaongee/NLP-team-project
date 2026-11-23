import { useMemo, useState } from 'react'
import { deleteFaq, listFaqs } from '../../api/faqs'
import type { Faq } from '../../api/types'
import { useFaqSync } from '../../realtime/useFaqSync'
import { useResource } from '../chat/useResource'
import FaqEditor from './FaqEditor'

const NONE: Faq[] = []

// 「자주 묻는 질문」 목록. 질문을 누르면 답이 펼쳐진다. 검색칸은 질문 · 답변을 함께 찾는다.
// 교사(editable): [＋ Q&A 추가] · 고치기 · 지우기(두 번 눌러 지움). 학부모: 보기만.
export default function FaqBoard({ editable }: { editable: boolean }) {
  const { data, setData, loaded, error, refresh } = useResource(listFaqs, NONE)
  useFaqSync(refresh)
  const [query, setQuery] = useState('')
  const [adding, setAdding] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null) // 한 번 누르면 확인, 한 번 더 누르면 지움
  const [actionError, setActionError] = useState<string | null>(null)

  const shown = useMemo(() => {
    const q = query.trim()
    return q === '' ? data : data.filter((f) => f.question.includes(q) || f.answer.includes(q))
  }, [data, query])

  const upsert = (f: Faq) =>
    setData((prev) => (prev.some((p) => p.id === f.id) ? prev.map((p) => (p.id === f.id ? f : p)) : [f, ...prev]))

  async function onDelete(id: number) {
    if (deletingId !== id) {
      setDeletingId(id)
      return
    }
    setActionError(null)
    try {
      await deleteFaq(id)
      setData((prev) => prev.filter((p) => p.id !== id))
    } catch (e) {
      setActionError(e instanceof Error ? e.message : '지우지 못했습니다')
    }
    setDeletingId(null)
  }

  return (
    <div className="faq-board">
      <div className="notice-heading">
        <h2>자주 묻는 질문</h2>
        {editable && !adding && (
          <button type="button" className="notice-create" onClick={() => setAdding(true)}>
            ＋ Q&A 추가
          </button>
        )}
      </div>
      <p className="sub">
        {editable ? '＋ Q&A 추가에서 대화를 고르면 그 대화를 보고 초안을 써 줘요.' : '선생님께 묻기 전에 먼저 찾아보세요.'}
      </p>
      {adding && (
        <FaqEditor
          onSaved={(f) => {
            upsert(f)
            setAdding(false)
          }}
          onCancel={() => setAdding(false)}
        />
      )}
      {data.length > 3 && (
        <input
          className="notice-input faq-search"
          type="search"
          placeholder="궁금한 내용 검색"
          aria-label="자주 묻는 질문 검색"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      )}
      {!loaded && !error && <p className="loading">불러오는 중</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      {actionError && <p className="alert" role="alert">{actionError}</p>}
      {loaded && data.length === 0 && !adding && (
        <div className="empty">{editable ? '등록한 Q&A 가 없어요' : '아직 등록된 질문이 없어요'}</div>
      )}
      {loaded && data.length > 0 && shown.length === 0 && <div className="empty">「{query.trim()}」 에 맞는 질문이 없어요</div>}
      {shown.map((f) =>
        editingId === f.id ? (
          <FaqEditor
            key={f.id}
            faq={f}
            onSaved={(saved) => {
              upsert(saved)
              setEditingId(null)
            }}
            onCancel={() => setEditingId(null)}
          />
        ) : (
          <details key={f.id} className="faq-item">
            <summary>
              <span className="faq-q">Q</span>
              <span className="faq-question">{f.question}</span>
            </summary>
            <p className="faq-answer">{f.answer}</p>
            {editable && (
              <div className="faq-item-actions">
                <button type="button" className="link-button" onClick={() => setEditingId(f.id)}>
                  고치기
                </button>
                <button
                  type="button"
                  className={`link-button${deletingId === f.id ? ' danger' : ''}`}
                  onClick={() => void onDelete(f.id)}
                  onBlur={() => setDeletingId((d) => (d === f.id ? null : d))}
                >
                  {deletingId === f.id ? '한 번 더 누르면 지워요' : '지우기'}
                </button>
              </div>
            )}
          </details>
        ),
      )}
    </div>
  )
}
