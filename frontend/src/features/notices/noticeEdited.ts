import type { Notice } from '../../api/types'

// 게시한 뒤에 고친 공지인지. 서버는 게시할 때 updated_at 을 건드리지 않으므로 updated_at > sent_at 이면 게시 후 수정이다.
export function editedAfterSend(n: Notice): boolean {
  if (n.status !== 'sent' || !n.sent_at) return false
  return new Date(n.updated_at).getTime() > new Date(n.sent_at).getTime()
}
