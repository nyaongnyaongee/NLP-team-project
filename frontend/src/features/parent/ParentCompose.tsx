import { useCallback, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { listStartable, startConversation } from '../../api/conversations'
import { sendMessage } from '../../api/messages'
import type { Startable } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { SCHOOL_NAME } from '../../components/AppShell'
import AddChild from '../chat/AddChild'
import { useResource } from '../chat/useResource'

const NONE: Startable[] = []
const MAX = 2000

// 「자주 쓰는 글」: 누르면 입력칸에 틀이 채워지고 첫 빈칸(○ 또는 (…))이 선택된다. {child} = 고른 자녀 이름
const TEMPLATES: { label: string; text: string }[] = [
  {
    label: '결석',
    text: '선생님 안녕하세요. {child}가 ○월 ○일에 (사유) 때문에 결석하려고 합니다.',
  },
  {
    label: '조퇴 · 지각',
    text: '선생님 안녕하세요. {child}가 ○월 ○일 ○시에 (사유)로 조퇴하려고 합니다. ○시쯤 데리러 가겠습니다.',
  },
  {
    label: '체험학습 신청',
    text: '선생님 안녕하세요. ○월 ○일부터 ○일까지 (사유)로 {child} 교외체험학습을 신청하려고 합니다. 신청서는 언제까지 내면 될까요?',
  },
  {
    label: '상담 요청',
    text: '선생님 안녕하세요. {child} (상담할 내용) 때문에 상담을 받고 싶습니다. 편하신 시간을 알려 주시면 맞추겠습니다.',
  },
]
const BLANK = /○|\([^)]*\)/

// 학부모 첫 화면 「메시지 작성」: 담임 카드(자녀가 여럿이면 골라서) + 글쓰기. 보내면 새 대화방이 열리고 그 방으로 간다 (문의마다 대화방)
export default function ParentCompose() {
  const { session } = useAuth()
  const navigate = useNavigate()
  const load = useCallback(() => listStartable(), [])
  const { data: kids, setData, loaded, error } = useResource(load, NONE)
  const [pickedId, setPickedId] = useState<number | null>(null)
  const [text, setText] = useState('')
  const [showTemplates, setShowTemplates] = useState(true)
  const textRef = useRef<HTMLTextAreaElement>(null)
  const [busy, setBusy] = useState(false)
  const [sendError, setSendError] = useState<string | null>(null)

  const picked = kids.find((k) => k.student_id === pickedId) ?? kids[0] ?? null
  const given = picked ? picked.student_name.replace(/^[가-힣](?=[가-힣]{2}$)/, '') : '아이' // 박지민 → 지민
  // 부르는 이름: 받침이 있으면 「이」를 붙인다 (지민 → 지민이가, 지우 → 지우가)
  const last = given.charCodeAt(given.length - 1)
  const childName = last >= 0xac00 && last <= 0xd7a3 && (last - 0xac00) % 28 !== 0 ? `${given}이` : given

  function applyTemplate(template: string) {
    const filled = template.replaceAll('{child}', childName)
    setText(filled)
    const m = BLANK.exec(filled)
    requestAnimationFrame(() => {
      const el = textRef.current
      if (!el) return
      el.focus()
      if (m) el.setSelectionRange(m.index, m.index + m[0].length)
    })
  }

  async function onSend() {
    const body = text.trim()
    if (!picked || body === '' || busy) return
    setBusy(true)
    setSendError(null)
    try {
      const conv = await startConversation(picked.student_id)
      await sendMessage(conv.id, body)
      setText('')
      navigate('/parent/chats', { state: { open: conv.id } })
    } catch (e) {
      setSendError(e instanceof Error ? e.message : '보내지 못했습니다')
      setBusy(false)
    }
  }

  return (
    <section className="compose-home">
      <h2 className="hero-title">
        선생님께
        <br />
        이야기를 전해보세요.
      </h2>
      <p className="sub">{session?.name} 학부모님의 소통 공간입니다.</p>

      {!loaded && !error && <p className="loading">불러오는 중</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      {loaded && kids.length === 0 && (
        <div className="empty">
          아직 연결된 자녀가 없어요.
          <br />
          담임 선생님께 받은 초대 코드로 자녀를 추가해 주세요.
        </div>
      )}
      <div className="teacher-cards" role={kids.length > 1 ? 'radiogroup' : undefined} aria-label="받는 선생님">
        {kids.map((k) => {
          const on = picked?.student_id === k.student_id
          return (
            <button
              key={k.student_id}
              type="button"
              className={`teacher-card${on ? ' on' : ''}`}
              role={kids.length > 1 ? 'radio' : undefined}
              aria-checked={kids.length > 1 ? on : undefined}
              onClick={() => setPickedId(k.student_id)}
            >
              <span className="avatar big">{k.teacher_name.slice(0, 1)}</span>
              <span>
                <b>{k.teacher_name} 선생님</b>
                <small>
                  {SCHOOL_NAME} · {k.student_name} 담임
                </small>
              </span>
            </button>
          )
        })}
      </div>
      {loaded && (
        <AddChild
          onAdded={(s) => {
            setData((rows) => [...rows, s])
            setPickedId(s.student_id)
          }}
        />
      )}

      {picked && (
        <>
          <div className="compose-head">
            <h3>메시지 작성</h3>
            <button type="button" className="link-button" onClick={() => setShowTemplates((v) => !v)}>
              {showTemplates ? '자주 쓰는 글 숨기기' : '자주 쓰는 글'}
            </button>
          </div>
          {showTemplates && (
            <div className="example-chips">
              {TEMPLATES.map((t) => (
                <button key={t.label} type="button" onClick={() => applyTemplate(t.text)}>
                  {t.label}
                </button>
              ))}
            </div>
          )}
          <textarea
            ref={textRef}
            className="compose-text"
            value={text}
            maxLength={MAX}
            onChange={(e) => setText(e.target.value)}
            placeholder="선생님께 전달할 내용을 적어주세요."
            aria-label={`${picked.teacher_name} 선생님께 보낼 메시지`}
          />
          {sendError && <p className="alert" role="alert">{sendError}</p>}
          <button type="button" className="primary send-big" onClick={() => void onSend()} disabled={busy || text.trim() === ''}>
            {busy ? (<><span className="spinner" />보내는 중</>) : '메시지 전송 ↑'}
          </button>
          <p className="char-count">{text.length}자</p>
        </>
      )}
    </section>
  )
}
