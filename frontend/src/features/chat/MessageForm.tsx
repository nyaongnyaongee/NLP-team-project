import {
  useImperativeHandle,
  useLayoutEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
  type Ref,
} from 'react'

// 입력창 밖에서 글을 읽고 채울 때 쓴다 (AI 답장 초안을 입력창에 채운다, S7)
export type MessageFormHandle = { getText: () => string; setText: (text: string) => void }

const MAX_HEIGHT = 132 // 입력칸이 글에 따라 늘어나는 최대 높이 (px), 넘으면 칸 안에서 스크롤

// 학부모·교사가 같이 쓰는 입력 막대 (메시지 앱 모양: 둥근 입력칸 + 동그란 보내기 단추).
// onSend 가 성공해야 입력을 비운다 (실패하면 입력 내용을 지우지 않는다, 명세 3.1).
// headerAction: 입력칸 왼쪽의 작은 단추 (교사의 「AI 초안」), beforeInput: 입력 줄 바로 위 (초안 메모 · 확인 항목)
// extraAction: 입력 줄 아래 단추 (지금은 쓰는 곳 없음, 예전 「대화 종료」 자리)
// Enter = 보내기, Shift+Enter = 줄바꿈. 터치 기기에서는 Enter 가 줄바꿈 (보내기는 단추로).
export default function MessageForm({
  id,
  label,
  onSend,
  handleRef,
  extraAction,
  headerAction,
  beforeInput,
}: {
  id: string
  label: string
  onSend: (text: string) => Promise<void>
  handleRef?: Ref<MessageFormHandle>
  extraAction?: ReactNode
  headerAction?: ReactNode
  beforeInput?: ReactNode
}) {
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // state 는 다음 렌더에야 바뀌므로, 더블클릭·엔터 연타로 두 번 전송되는 것을 ref 로 막는다.
  const sendingRef = useRef(false)
  const area = useRef<HTMLTextAreaElement>(null)

  useImperativeHandle(handleRef, () => ({ getText: () => text, setText }), [text])

  // 글에 맞춰 입력칸 높이를 늘리고 줄인다
  useLayoutEffect(() => {
    const el = area.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`
  }, [text])

  async function submit() {
    const body = text.trim()
    if (body === '' || sendingRef.current) return
    sendingRef.current = true
    setSending(true)
    setError(null)
    try {
      await onSend(body)
      setText('')
    } catch (err) {
      setError(err instanceof Error ? err.message : '보내지 못했습니다')
    } finally {
      sendingRef.current = false
      setSending(false)
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    void submit()
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    const touch = window.matchMedia?.('(pointer: coarse)').matches
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing && !touch) {
      e.preventDefault()
      void submit()
    }
  }

  const empty = text.trim() === ''
  return (
    <form className="reply composer" onSubmit={onSubmit}>
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      {beforeInput}
      <div className="composer-row">
        {headerAction}
        <div className="composer-field">
          <textarea
            id={id}
            ref={area}
            rows={1}
            value={text}
            placeholder={label}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onKeyDown}
          />
          <button type="submit" className="send" disabled={sending || empty} aria-label={sending ? '보내는 중' : '보내기'}>
            {sending ? (
              <span className="spinner" />
            ) : (
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 19V6M6 11l6-6 6 6" />
              </svg>
            )}
          </button>
        </div>
      </div>
      {error && <p className="alert" role="alert">{error}</p>}
      {extraAction && <div className="reply-actions">{extraAction}</div>}
    </form>
  )
}
