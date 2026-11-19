import { useCallback, useState } from 'react'
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

// 「예시로 체험하기」: 누르면 입력칸에 채워진다 (시연용). {child} = 고른 자녀 이름
const EXAMPLES: { label: string; text: string; wide?: boolean }[] = [
  {
    label: '결석 안내',
    text: '선생님 안녕하세요. {child}가 어젯밤부터 열이 나서 오늘 병원에 들렀다가 오후에 등교하려고 합니다. 오전 수업 내용은 어떻게 챙기면 될까요?',
  },
  {
    label: '상담 요청',
    text: '선생님, {child} 교우 관계 때문에 한번 상담을 받고 싶습니다. 다음 주 중에 편하신 시간을 알려 주시면 맞춰서 찾아뵙겠습니다.',
  },
  {
    label: '유해표현 포함',
    text: '아니 선생님 도대체 애를 어떻게 보시는 거예요? {child}가 또 다쳐서 왔는데 연락 한 통이 없네요. 이게 말이 됩니까? 오늘 안에 꼭 연락 주세요.',
  },
  {
    label: '반복 민원 시연 · 앞자리·매일 칭찬 요구',
    wide: true,
    text: '선생님 몇 번을 말씀드려야 알아들으세요? {child} 자리 맨 앞으로 바꿔 달라고 했잖아요. 그리고 매일 칭찬 한마디씩 해서 알림장에 적어 주세요. 이번 주 금요일까지 안 바뀌면 교장실에 직접 가겠습니다.',
  },
]

// 학부모 첫 화면 「메시지 작성」: 담임 카드(자녀가 여럿이면 골라서) + 글쓰기. 보내면 새 대화방이 열리고 그 방으로 간다 (문의마다 대화방)
export default function ParentCompose() {
  const { session } = useAuth()
  const navigate = useNavigate()
  const load = useCallback(() => listStartable(), [])
  const { data: kids, setData, loaded, error } = useResource(load, NONE)
  const [pickedId, setPickedId] = useState<number | null>(null)
  const [text, setText] = useState('')
  const [showExamples, setShowExamples] = useState(true)
  const [busy, setBusy] = useState(false)
  const [sendError, setSendError] = useState<string | null>(null)

  const picked = kids.find((k) => k.student_id === pickedId) ?? kids[0] ?? null
  const given = picked ? picked.student_name.replace(/^[가-힣](?=[가-힣]{2}$)/, '') : '아이' // 박지민 → 지민
  // 부르는 이름: 받침이 있으면 「이」를 붙인다 (지민 → 지민이가, 지우 → 지우가)
  const last = given.charCodeAt(given.length - 1)
  const childName = last >= 0xac00 && last <= 0xd7a3 && (last - 0xac00) % 28 !== 0 ? `${given}이` : given

  async function onSend() {
    const body = text.trim()
    if (!picked || body === '' || busy) return
    setBusy(true)
    setSendError(null)
    try {
      const conv = await startConversation(picked.student_id)
      await sendMessage(conv.id, body)
      setText('')
      navigate(`/parent/chats?chat=${conv.id}`)
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
            <button type="button" className="link-button" onClick={() => setShowExamples((v) => !v)}>
              {showExamples ? '예시 숨기기' : '예시로 체험하기'}
            </button>
          </div>
          {showExamples && (
            <div className="example-chips">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex.label}
                  type="button"
                  className={ex.wide ? 'wide' : ''}
                  onClick={() => setText(ex.text.replaceAll('{child}', childName))}
                >
                  {ex.label}
                </button>
              ))}
            </div>
          )}
          <textarea
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
