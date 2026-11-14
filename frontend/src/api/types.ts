// 명세 3.2: 서버 응답 타입은 이 파일 한 곳에만 둔다 (4.4-2).

export type Role = 'parent' | 'teacher' | 'complaint_team'

export type LoginRes = { token: string; name: string; role: Role }

export type Conversation = {
  id: number
  teacher_id: number
  parent_id: number
  student_name: string
  status: 'open' | 'closed'
  extract?: { status: 'pending' | 'done' | 'failed'; error?: string; count?: number; at?: string } | null // 교사에게만 옴
  created_at: string
  // report, reported_at 은 선언하지 않는다 (치명 2)
}

export type MessageStatus = 'pending' | 'done' | 'failed' | 'skip'

export type Message = {
  id: number
  sender_id: number
  raw_text: string | null
  refined_text: string | null // 교사에게만
  analysis: Record<string, unknown> | null // 교사에게만, 모양 자유. 실패 시 { error: string }
  status: MessageStatus // 학부모 화면은 읽지 않는다 (중대 5)
  created_at: string
}

export type Task = {
  id: number
  conversation_id: number
  student_name: string
  kind: 'todo' | 'event'
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
}
