import { useState } from 'react'
import StartConversation from '../chat/StartConversation'
import { useConversations } from '../chat/useConversations'
import TeacherThread from './TeacherThread'

// 교사 "대화 목록" 탭 (S2~S4 의 교사 화면). 대화를 고르면 목록 대신 그 대화방이 열리고, "‹ 대화 목록"으로 돌아온다 (데모와 같은 흐름).
export default function ConversationsTab() {
  const { conversations, loading, error, add } = useConversations()
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [starting, setStarting] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const selected = conversations.find((c) => c.id === selectedId) ?? null

  // 403·404 를 받으면 안내를 남기고 목록으로 돌아온다 (명세 3.1)
  const leave = (message: string) => {
    setNotice(message)
    setSelectedId(null)
  }
  const select = (id: number) => {
    setNotice(null)
    setSelectedId(id)
  }

  if (selected) {
    return (
      <TeacherThread
        key={selected.id}
        conversation={selected}
        onLeave={leave}
        onBack={() => setSelectedId(null)}
      />
    )
  }

  return (
    <section>
      <div className="eyebrow">CONVERSATIONS</div>
      <div className="notice-heading">
        <h2>대화 목록</h2>
        {!starting && (
          <button type="button" className="notice-create" onClick={() => setStarting(true)}>
            ＋ 새 대화
          </button>
        )}
      </div>
      {starting && (
        <StartConversation
          role="teacher"
          onCancel={() => setStarting(false)}
          onStarted={(c) => {
            add(c)
            setStarting(false)
            select(c.id)
          }}
        />
      )}
      {loading && <p className="loading">불러오는 중</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      {notice && <p className="alert" role="alert">{notice}</p>}
      {!loading && !error && conversations.length === 0 && (
        <div className="empty">
          <div className="big">▤</div>아직 대화가 없어요. 「＋ 새 대화」로 학부모와 대화를 시작하세요
        </div>
      )}
      {/* 대화 목록은 학생 이름으로 표시한다 (중대 3) */}
      <ul className="plain-list">
        {conversations.map((c) => (
          <li key={c.id}>
            <button type="button" className="row" onClick={() => select(c.id)} aria-pressed={c.id === selectedId}>
              <span className="avatar">{c.student_name.slice(0, 1)}</span>
              <span className="row-main">
                <span className="row-title">
                  <b>{c.student_name}</b>
                </span>
                <span className="tag">{c.status === 'closed' ? '대화 종료' : '대화 중'}</span>
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
