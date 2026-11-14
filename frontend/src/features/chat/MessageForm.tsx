import { useImperativeHandle, useRef, useState, type FormEvent, type ReactNode, type Ref } from 'react'

// 입력창 밖에서 글을 읽고 채울 때 쓴다 (AI 답장 초안을 입력창에 채운다, S7)
export type MessageFormHandle = { getText: () => string; setText: (text: string) => void }

// 학부모·교사가 같이 쓰는 입력창. onSend 가 성공해야 입력을 비운다 (실패하면 입력 내용을 지우지 않는다, 명세 3.1).
// extraAction: 보내기 버튼 왼쪽에 놓을 버튼 (교사 화면의 "대화 종료", 데모의 .reply-actions 배치)
export default function MessageForm({
  id,
  label,
  onSend,
  handleRef,
  extraAction,
}: {
  id: string
  label: string
  onSend: (text: string) => Promise<void>
  handleRef?: Ref<MessageFormHandle>
  extraAction?: ReactNode
}) {
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // state 는 다음 렌더에야 바뀌므로, 더블클릭·엔터 연타로 두 번 전송되는 것을 ref 로 막는다.
  const sendingRef = useRef(false)

  useImperativeHandle(handleRef, () => ({ getText: () => text, setText }), [text])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
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

  return (
    <form className="reply" onSubmit={onSubmit}>
      <label htmlFor={id} className="info">
        {label}
      </label>
      <textarea id={id} value={text} onChange={(e) => setText(e.target.value)} rows={3} />
      {error && <p className="alert" role="alert">{error}</p>}
      <div className={extraAction ? 'reply-actions' : 'parent-send'}>
        {extraAction}
        <button type="submit" className="primary" disabled={sending || text.trim() === ''}>
          {sending ? (<><span className="spinner" />보내는 중</>) : '보내기'}
        </button>
      </div>
    </form>
  )
}
