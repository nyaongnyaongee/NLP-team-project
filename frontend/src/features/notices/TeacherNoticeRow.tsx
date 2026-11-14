import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../../api/client'
import { deleteNotice, sendNotice } from '../../api/notices'
import type { Notice } from '../../api/types'
import { formatTime } from '../chat/formatTime'

// 교사 공지 목록의 한 장(데모의 .notice-card). 초안은 수정·삭제·게시, 게시된 공지는 보기만 (수정·삭제 버튼을 보이지 않는다).
export default function TeacherNoticeRow({
  notice,
  onChanged,
  onRemoved,
  onConflict,
}: {
  notice: Notice
  onChanged: (notice: Notice) => void
  onRemoved: (id: number) => void
  onConflict: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const busyRef = useRef(false)
  const sent = notice.status === 'sent'

  async function run(action: () => Promise<void>) {
    if (busyRef.current) return
    busyRef.current = true
    setBusy(true)
    setError(null)
    try {
      await action()
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) onRemoved(notice.id) // 이미 지워졌다 (명세 3.1)
      else {
        setError(e instanceof Error ? e.message : '요청에 실패했습니다') // 409 는 detail 문장 그대로
        if (e instanceof ApiError && e.status === 409) onConflict()
      }
    } finally {
      busyRef.current = false
      setBusy(false)
    }
  }

  const onDelete = () => {
    if (!window.confirm(`"${notice.title}" 공지를 삭제할까요?`)) return
    void run(async () => {
      await deleteNotice(notice.id)
      onRemoved(notice.id)
    })
  }

  const onSend = () => {
    if (!window.confirm(`"${notice.title}" 공지를 게시할까요? 게시하면 학부모에게 보이고, 고치거나 지울 수 없어요.`)) return
    void run(async () => onChanged(await sendNotice(notice.id)))
  }

  const to = `/teacher/notices/${notice.id}`
  return (
    <article className="notice-card">
      <Link className="notice-link" to={to}>
        <span className="tag">{sent ? `게시됨${notice.sent_at ? ` · ${formatTime(notice.sent_at)}` : ''}` : '초안'}</span>
        <h3>{notice.title}</h3>
        <p>{notice.body}</p>
      </Link>
      {error && <p className="alert" role="alert" style={{ margin: '0 16px 12px' }}>{error}</p>}
      <div className="notice-foot">
        {sent ? (
          <Link className="notice-detail" to={to}>
            보기
          </Link>
        ) : (
          <>
            <Link className="notice-detail" to={to}>
              수정
            </Link>
            <button type="button" className="notice-detail" onClick={onDelete} disabled={busy}>
              삭제
            </button>
            <button type="button" className="notice-chat" onClick={onSend} disabled={busy}>
              게시
            </button>
          </>
        )}
      </div>
    </article>
  )
}
