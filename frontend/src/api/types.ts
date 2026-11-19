// 명세 3.2: 서버 응답 타입은 이 파일 한 곳에만 둔다 (4.4-2).

export type Role = 'parent' | 'teacher' | 'complaint_team'

export type LoginRes = { token: string; name: string; role: Role }

export type Conversation = {
  id: number
  teacher_id: number
  parent_id: number
  student_name: string
  teacher_name?: string | null // 담임 이름 (학부모 화면의 대화 상대 「김민지 선생님」)
  parent_name?: string | null // 학부모 이름 (교사 화면의 대화 상대 「박서연 (박지민 부모)」)
  student_id?: number | null // 반 명단의 학생과 이어진 대화면 그 학생 번호 (학생 메모)
  status: 'open' | 'closed'
  extract?: { status: 'pending' | 'done' | 'failed'; error?: string; count?: number; at?: string } | null // 교사에게만 옴
  created_at: string
  closed_at?: string | null // 대화를 닫은 시각 (종료 순 정렬). 열린 대화 · 예전에 닫은 대화는 null
  last_message_at?: string | null // 목록에서만 옴. 마지막 메시지 시각 (없으면 null)
  preview?: ConversationPreview // 목록에서만 옴
  unread?: number // 목록에서만 옴. 상대가 보낸 글 중 내가 아직 안 읽은 수
  // report, reported_at 은 선언하지 않는다 (치명 2)
}

// 목록 한 줄 요약. Claude 를 새로 부르지 않고 정제 분석을 다시 쓴다.
// last.text: 보는 사람 기준 마지막 글 (교사 = 정제문 · 통과 원문). 처리 전 · 실패한 학부모 글은 null → status 로 문구
// summary · topic · requests: 교사 · 학부모 둘 다. summary = 첫 학부모 글의 한 줄 요약, requests = summary 가 없는 예전 글용
export type ConversationPreview = {
  last: { text: string | null; mine: boolean; status: MessageStatus } | null
  summary?: string | null
  topic?: string | null
  requests?: string[]
}

// 대화를 시작할 수 있는 학생 (교사 = 학부모가 등록된 반 학생, 학부모 = 내 아이)
export type Startable = {
  student_id: number
  student_name: string
  teacher_name: string
  parent_name: string
}

export type MessageStatus = 'pending' | 'done' | 'failed' | 'skip'

export type Message = {
  id: number
  sender_id: number
  raw_text: string | null
  refined_text: string | null // 교사: 정제문 / 학부모: refined 인 자기 글만
  analysis: Record<string, unknown> | null // 교사에게만, 모양 자유. 실패 시 { error: string }
  status: MessageStatus // 학부모 화면은 읽지 않는다 (중대 5)
  refined?: boolean | null // 학부모에게만: 내 글이 다듬어져 선생님께 갔는지 (그때만 refined_text 가 옴)
  created_at: string
}

export type Task = {
  id: number
  conversation_id: number | null // null = 교사가 직접 등록한 반 전체 일정
  student_name: string | null
  kind: 'todo' | 'event'
  shared?: boolean // 일정: 학부모 캘린더에 보임
  title: string
  due_text: string | null // 대화에 적힌 표현 그대로
  due_at: string | null // 시각이 없으면 그날 00:00 (한국 시각)
  status: 'candidate' | 'added' | 'done'
  created_at: string
}

// AI 초안 (S7). 서버는 초안을 저장하지 않는다: 교사가 고쳐서 보통 메시지·공지로 보낸다.
export type ReplyDraft = { draft: string; check: string[] } // check: 보내기 전에 교사가 확인할 것
export type NoticeDraft = { title: string; body: string; check: string[] }

export type Notice = {
  id: number
  teacher_id: number
  title: string // 1~100자
  body: string // 1~5000자
  status: 'draft' | 'sent'
  created_at: string
  updated_at: string
  sent_at: string | null
  comment_count?: number // 댓글 수 (서버 schemas/notice.py)
}

// 공지 댓글 (게시된 공지에 교사 · 받는 학부모가 단다)
export type NoticeComment = {
  id: number
  notice_id: number
  author_id: number
  author_role: 'teacher' | 'parent'
  author_name: string // 「김민지 선생님」 · 「박지민 학부모」
  body: string // 1~1000자
  created_at: string
  mine: boolean
  can_delete: boolean // 내 댓글, 또는 내 공지에 달린 댓글(교사)
}

// 학부모 캘린더의 일정 (선생님이 공유한 것만, 서버 schemas/todo.py ParentEventOut)
export type ParentEvent = {
  id: number
  conversation_id: number | null
  student_name: string | null // null = 반 전체
  teacher_name: string
  title: string
  due_text: string | null
  due_at: string | null
  status: 'added' | 'done'
}
