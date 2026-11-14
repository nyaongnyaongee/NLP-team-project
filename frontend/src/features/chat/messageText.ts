import type { Message } from '../../api/types'

// 명세 3.3: "무엇을 보여줄지"는 이 파일에서만 정한다. 화면은 결과만 그린다.

export type TeacherView =
  | { kind: 'text'; text: string }
  | { kind: 'pending' }
  | { kind: 'failed'; reason: string | null }
  | { kind: 'empty' } // 완료인데 보여줄 글이 없는 경우, 알 수 없는 상태

export type ParentView = { kind: 'text'; text: string }

function errorOf(analysis: Message['analysis']): string | null {
  const e = analysis?.error
  return typeof e === 'string' ? e : null
}

// 교사 화면. pending, failed 에서는 raw_text 를 읽지 않는다 (서버가 막아 주더라도 방어선 하나 더).
export function teacherView(m: Message): TeacherView {
  switch (m.status) {
    case 'skip':
      return { kind: 'text', text: m.raw_text ?? '' } // 내가 보낸 답장
    case 'pending':
      return { kind: 'pending' }
    case 'failed':
      return { kind: 'failed', reason: errorOf(m.analysis) }
    case 'done': {
      const text = m.refined_text ?? m.raw_text // 정제문, 없으면 통과된 원문
      return text === null ? { kind: 'empty' } : { kind: 'text', text }
    }
    default:
      return { kind: 'empty' } // 모르는 상태에서는 원문을 읽지 않는다
  }
}

// 학부모 화면. status 는 보지 않는다 (중대 5).
export function parentView(m: Message): ParentView {
  return { kind: 'text', text: m.raw_text ?? '' }
}
