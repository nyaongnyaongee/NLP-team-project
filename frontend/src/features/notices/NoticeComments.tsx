import { useCallback, useRef, useState, type FormEvent } from 'react'
import { addComment, deleteComment, listComments } from '../../api/notices'
import type { NoticeComment } from '../../api/types'
import { useSync } from '../../realtime/useSync'
import { formatTime } from '../chat/formatTime'
import { useResource } from '../chat/useResource'

export const COMMENT_MAX = 1000
const NO_COMMENTS: NoticeComment[] = []
const countChars = (s: string) => [...s].length

// 게시된 공지 아래 댓글 (교사 · 학부모 같이 씀). 누가 달거나 지우면 {"type":"notice"} 알림으로 다시 읽는다.
// 댓글은 정제하지 않고 쓴 그대로 반 학부모 모두와 선생님에게 보인다.
export default function NoticeComments({ noticeId }: { noticeId: number }) {
  const load = useCallback(() => listComments(noticeId), [noticeId])
  const { data: comments, loaded, error, refresh } = useResource(load, NO_COMMENTS)
  useSync(['notice-comments', noticeId], refresh, (e) => e.type === 'notice' && (e.noticeId === noticeId || e.noticeId === null))

  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const busyRef = useRef(false)
  const len = countChars(text)

  async function run(action: () => Promise<void>) {
    if (busyRef.current) return
    busyRef.current = true
    setBusy(true)
    setActionError(null)
    try {
      await action()
      await refresh()
    } catch (e) {
      setActionError(e instanceof Error ? e.message : '요청에 실패했습니다')
    } finally {
      busyRef.current = false
      setBusy(false)
    }
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    const body = text.trim()
    if (!body || len > COMMENT_MAX) return
    void run(async () => {
      await addComment(noticeId, body)
      setText('')
    })
  }

  const onDelete = (c: NoticeComment) => {
    if (!window.confirm(c.mine ? '내 댓글을 삭제할까요?' : `${c.author_name}의 댓글을 삭제할까요?`)) return
    void run(() => deleteComment(noticeId, c.id))
  }

  return (
    <section className="notice-comments" aria-label="댓글">
      <h3>댓글 {comments.length > 0 && <span>{comments.length}</span>}</h3>
      {!loaded && error === null && <p className="loading">불러오는 중</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      {loaded && comments.length === 0 && !error && <p className="comment-empty">아직 댓글이 없어요</p>}
      <ul>
        {comments.map((c) => (
          <li key={c.id} className={`comment ${c.author_role === 'teacher' ? 'by-teacher' : ''}`}>
            <div className="comment-head">
              <b>{c.author_name}</b>
              {c.mine && <span className="comment-mine">나</span>}
              <small>{formatTime(c.created_at)}</small>
              {c.can_delete && (
                <button type="button" className="comment-delete" onClick={() => onDelete(c)} disabled={busy}>
                  삭제
                </button>
              )}
            </div>
            <div className="comment-body">{c.body}</div>
          </li>
        ))}
      </ul>
      <form className="comment-form" onSubmit={onSubmit}>
        <label htmlFor={`comment-${noticeId}`} className="sr-only">댓글 쓰기</label>
        <textarea
          id={`comment-${noticeId}`}
          value={text}
          rows={2}
          placeholder="댓글을 남겨 주세요 (반 학부모 모두와 선생님이 봐요)"
          onChange={(e) => setText(e.target.value)}
        />
        <div className="comment-form-foot">
          <span className={`char ${len > COMMENT_MAX ? 'over' : ''}`}>{len}/{COMMENT_MAX}</span>
          <button type="submit" className="notice-chat" disabled={busy || text.trim() === '' || len > COMMENT_MAX}>
            {busy ? '보내는 중' : '댓글 달기'}
          </button>
        </div>
      </form>
      {actionError && <p className="alert" role="alert">{actionError}</p>}
    </section>
  )
}
