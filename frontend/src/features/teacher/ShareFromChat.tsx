import { useState } from 'react'
import ChatNoticeEditor from '../notices/ChatNoticeEditor'
import FaqEditor from '../faq/FaqEditor'

export type ShareResult = 'faq' | 'notice-sent' | 'notice-draft'
type Kind = 'faq' | 'notice'

// 교사 대화창의 「공지 · Q&A」 패널: 이 대화에서 나온 내용을 반 학부모 모두에게 알릴 꼴을 고른다.
// 고르면 그 종류의 초안을 대화를 보고 바로 만든다 (한 번 연 종류는 다시 골라도 새로 만들지 않고 쓰던 그대로).
export default function ShareFromChat({
  conversationId,
  onDone,
  onCancel,
}: {
  conversationId: number
  onDone: (result: ShareResult) => void
  onCancel: () => void
}) {
  const [kind, setKind] = useState<Kind>('faq')
  const [opened, setOpened] = useState<Set<Kind>>(() => new Set<Kind>(['faq']))
  const pick = (k: Kind) => {
    setKind(k)
    setOpened((prev) => (prev.has(k) ? prev : new Set(prev).add(k)))
  }

  return (
    <div className="memo-panel faq-panel">
      <div className="chips share-kind" role="group" aria-label="무엇으로 만들까요">
        <button type="button" className={kind === 'faq' ? 'active' : ''} aria-pressed={kind === 'faq'} onClick={() => pick('faq')}>
          자주 묻는 질문
        </button>
        <button type="button" className={kind === 'notice' ? 'active' : ''} aria-pressed={kind === 'notice'} onClick={() => pick('notice')}>
          공지
        </button>
      </div>
      <div hidden={kind !== 'faq'}>
        <FaqEditor conversationId={conversationId} onSaved={() => onDone('faq')} onCancel={onCancel} />
      </div>
      {opened.has('notice') && (
        <div hidden={kind !== 'notice'}>
          <ChatNoticeEditor
            conversationId={conversationId}
            onDone={(r) => onDone(r === 'sent' ? 'notice-sent' : 'notice-draft')}
            onCancel={onCancel}
          />
        </div>
      )}
    </div>
  )
}
