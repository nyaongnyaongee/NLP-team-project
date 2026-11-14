import type { Notice } from '../../api/types'
import { formatTime } from '../chat/formatTime'
import { editedAfterSend } from './noticeEdited'

// 공지 한 건을 읽기 전용으로 보여 준다 (학부모 상세). 본문은 {text} 로만 그리고 줄바꿈은 유지한다.
export default function NoticeView({ notice }: { notice: Notice }) {
  return (
    <article className="notice-detail-body">
      <span className="tag">학급 공지</span>
      <h2>{notice.title}</h2>
      {notice.sent_at && (
        <p className="sub">
          {formatTime(notice.sent_at)}
          {editedAfterSend(notice) && ` · 수정됨 ${formatTime(notice.updated_at)}`}
        </p>
      )}
      <div className="notice-content">{notice.body}</div>
    </article>
  )
}
