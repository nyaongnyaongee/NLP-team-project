import { useMemo, useState } from 'react'
import { Route, Routes, useNavigate, useParams } from 'react-router-dom'
import { startConversation } from '../../api/conversations'
import { listStudents, type Student } from '../../api/students'
import ConversationList from '../chat/ConversationList'
import { useConversations } from '../chat/useConversations'
import { useResource } from '../chat/useResource'
import { useSync } from '../../realtime/useSync'
import InviteCard from './InviteCard'
import { MemoPanel } from './StudentMemo'
import { useStudentMemo } from './useStudentMemo'

const NONE: Student[] = []

// 교사 「학생」 탭: 반 학생 목록 → 학생 한 명 (메모장 + 그 학생과의 대화). 주소 /teacher/students/:id
export default function StudentsTab() {
  const { data: students, loaded, error, refresh } = useResource(listStudents, NONE)
  useSync('students', () => void refresh(), (e) => e.type === 'students') // 초대 코드로 새 학부모가 들어오면
  const { conversations } = useConversations()
  return (
    <Routes>
      <Route index element={<StudentList students={students} loading={!loaded && !error} error={error} conversations={conversations} />} />
      <Route path=":id" element={<StudentDetail students={students} conversations={conversations} />} />
    </Routes>
  )
}

type Conversations = ReturnType<typeof useConversations>['conversations']

function StudentList({
  students,
  loading,
  error,
  conversations,
}: {
  students: Student[]
  loading: boolean
  error: string | null
  conversations: Conversations
}) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const shown = useMemo(() => {
    const q = query.trim()
    return q ? students.filter((s) => s.name.includes(q)) : students
  }, [students, query])

  return (
    <section>
      <div className="eyebrow">MY CLASS</div>
      <div className="tool-heading">
        <h2>우리 반 학생</h2>
        <span className="muted">{students.length}명</span>
      </div>
      <InviteCard />
      <input
        className="notice-input student-search"
        type="search"
        placeholder="이름 검색"
        aria-label="학생 이름 검색"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {loading && <p className="loading">불러오는 중</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      {!loading && !error && shown.length === 0 && <div className="empty">{query ? '찾는 학생이 없어요' : '반 학생이 없어요'}</div>}
      <ul className="plain-list">
        {shown.map((s) => {
          const mine = conversations.filter((c) => c.student_id === s.id)
          const open = mine.filter((c) => c.status === 'open').length
          return (
            <li key={s.id}>
              <button type="button" className="row student-line" onClick={() => navigate(String(s.id))}>
                <span className="avatar">{s.name.slice(0, 1)}</span>
                <span className="row-main">
                  <span className="row-title">
                    <span className="row-name">
                      <b>{s.name}</b>
                      {s.has_memo && <span className="memo-dot" aria-label="메모 있음" />}
                    </span>
                  </span>
                  <span className="row-last">
                    {mine.length === 0 ? '대화 없음' : `대화 ${mine.length}개${open ? ` · 진행 중 ${open}` : ''}`}
                  </span>
                </span>
                <span className="muted" aria-hidden="true">
                  ›
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

function StudentDetail({ students, conversations }: { students: Student[]; conversations: Conversations }) {
  const { id } = useParams()
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const student = students.find((s) => String(s.id) === id)
  if (!student) {
    return (
      <section>
        <button type="button" className="back" onClick={() => navigate('/teacher/students')}>
          ‹ 학생
        </button>
        <p className="loading">{students.length ? '찾을 수 없는 학생입니다' : '불러오는 중'}</p>
      </section>
    )
  }
  const mine = conversations.filter((c) => c.student_id === student.id)
  const openChat = (conversationId: number) => navigate('/teacher', { state: { open: conversationId } })

  const start = async () => {
    setBusy(true)
    setError(null)
    try {
      openChat((await startConversation(student.id)).id)
    } catch (e) {
      setError(e instanceof Error ? e.message : '대화를 시작하지 못했습니다')
      setBusy(false)
    }
  }

  return (
    <section>
      <div className="chat-head">
        <button type="button" className="back" onClick={() => navigate('/teacher/students')}>
          ‹ 학생
        </button>
      </div>
      <div className="chat-person">
        <span className="avatar">{student.name.slice(0, 1)}</span>
        <div>
          <b>{student.name}</b>
        </div>
      </div>
      <div className="section-title">
        <h3>메모</h3>
      </div>
      <StudentMemoBox key={student.id} studentId={student.id} studentName={student.name} />

      <div className="section-title">
        <h3>대화</h3>
        <button type="button" className="manual-add" onClick={() => void start()} disabled={busy}>
          ＋ 새 대화
        </button>
      </div>
      {error && <p className="alert" role="alert">{error}</p>}
      {mine.length === 0 && <div className="empty">이 학생과 나눈 대화가 없어요</div>}
      <ConversationList conversations={mine} onSelect={openChat} />
    </section>
  )
}

// 학생 탭: 메모 칸을 늘 펼쳐 둔다
function StudentMemoBox({ studentId, studentName }: { studentId: number; studentName: string }) {
  const memo = useStudentMemo(studentId)
  return <MemoPanel memo={memo} studentName={studentName} />
}
