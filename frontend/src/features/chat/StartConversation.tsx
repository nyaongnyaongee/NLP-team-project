import { useCallback, useRef, useState } from 'react'
import { listStartable, startConversation } from '../../api/conversations'
import type { Conversation, Startable } from '../../api/types'
import { useResource } from './useResource'

const NONE: Startable[] = []

// 대화 시작: 학생을 고르면 열린 대화가 있으면 그 대화를, 없으면 새 대화를 연다.
// 교사 = 학부모가 등록된 반 학생 목록, 학부모 = 내 아이 목록 (서버가 역할로 거른다).
export default function StartConversation({
  role,
  onStarted,
  onCancel,
}: {
  role: 'teacher' | 'parent'
  onStarted: (c: Conversation) => void
  onCancel?: () => void
}) {
  const load = useCallback(() => listStartable(), [])
  const { data, loaded, error } = useResource(load, NONE)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [startError, setStartError] = useState<string | null>(null)
  const busyRef = useRef(false)

  async function start(s: Startable) {
    if (busyRef.current) return
    busyRef.current = true
    setBusyId(s.student_id)
    setStartError(null)
    try {
      onStarted(await startConversation(s.student_id))
    } catch (e) {
      setStartError(e instanceof Error ? e.message : '대화를 시작하지 못했습니다')
    } finally {
      busyRef.current = false
      setBusyId(null)
    }
  }

  return (
    <section className="start-conversation">
      <div className="notice-heading">
        <h3>{role === 'teacher' ? '새 대화 — 학생 고르기' : '선생님께 문의하기'}</h3>
        {onCancel && (
          <button type="button" className="notice-detail" onClick={onCancel}>
            닫기
          </button>
        )}
      </div>
      {!loaded && error === null && <p className="loading">불러오는 중</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      {startError && <p className="alert" role="alert">{startError}</p>}
      {loaded && !error && data.length === 0 && (
        <p className="sub">
          {role === 'teacher' ? '학부모가 등록된 학생이 없어요' : '등록된 자녀가 없어요. 학교에 문의해 주세요'}
        </p>
      )}
      <ul className="plain-list">
        {data.map((s) => (
          <li key={s.student_id}>
            <button type="button" className="row" onClick={() => void start(s)} disabled={busyId !== null}>
              <span className="avatar">{s.student_name.slice(0, 1)}</span>
              <span className="row-main">
                <span className="row-title">
                  <b>{s.student_name}</b>
                  <small>{role === 'teacher' ? `학부모 ${s.parent_name}` : `담임 ${s.teacher_name} 선생님`}</small>
                </span>
                <span className="tag">
                  {busyId === s.student_id ? '여는 중…' : s.open_conversation_id ? '대화 이어가기' : '대화 시작'}
                </span>
              </span>
              <span className="muted" aria-hidden="true">
                ›
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
