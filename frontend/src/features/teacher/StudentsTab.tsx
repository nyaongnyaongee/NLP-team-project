import { useCallback, useMemo, useState } from 'react'
import { Route, Routes, useLocation, useNavigate, useParams } from 'react-router-dom'
import { listConversations, startConversation } from '../../api/conversations'
import type { Conversation } from '../../api/types'
import { listStudents, type Student } from '../../api/students'
import ConversationList from '../chat/ConversationList'
import SortSelect, { type SortControl } from '../chat/SortSelect'
import StatusFilter from '../chat/StatusFilter'
import { sortConversations } from '../chat/sortConversations'
import { usePersistedSort } from '../chat/usePersistedSort'
import { useStatusFilter } from '../chat/useStatusFilter'
import { useConversations } from '../chat/useConversations'
import { useResource } from '../chat/useResource'
import { useSync } from '../../realtime/useSync'
import InviteCard from './InviteCard'
import { MemoPanel } from './StudentMemo'
import TeacherThread from './TeacherThread'
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

// 학생 정렬: 이름 순 (가나다, 처음은 오름차순) · 진행 중 대화 순 (처음은 진행 중 대화가 많은 학생이 위, 같으면 이름 순). 방향은 항목을 한 번 더 눌러 바꾼다
type StudentSortKey = 'name' | 'open'
const STUDENT_SORTS: readonly StudentSortKey[] = ['name', 'open']
const STUDENT_SORT_OPTIONS = [
  { value: 'name', label: '이름 순' },
  { value: 'open', label: '진행 중 대화 순' },
]
const studentDefaultDesc = (key: StudentSortKey) => key !== 'name'
const byName = (a: Student, b: Student) => a.name.localeCompare(b.name, 'ko') || a.id - b.id

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
  const [sort, setSort] = usePersistedSort<StudentSortKey>('ieum:sort:v2:students', STUDENT_SORTS, 'name', studentDefaultDesc)
  const openCounts = useMemo(() => {
    const m = new Map<number, number>()
    for (const c of conversations) {
      if (c.status === 'open' && c.student_id != null) m.set(c.student_id, (m.get(c.student_id) ?? 0) + 1)
    }
    return m
  }, [conversations])
  const shown = useMemo(() => {
    const q = query.trim()
    const list = q ? students.filter((s) => s.name.includes(q)) : [...students]
    const sign = sort.desc ? -1 : 1
    if (sort.key === 'open') {
      return list.sort((a, b) => sign * ((openCounts.get(a.id) ?? 0) - (openCounts.get(b.id) ?? 0) || byName(a, b)))
    }
    return list.sort((a, b) => sign * byName(a, b))
  }, [students, query, sort, openCounts])
  const sortControl: SortControl = {
    options: STUDENT_SORT_OPTIONS,
    value: sort.key,
    desc: sort.desc,
    onPick: (value) => setSort(value === 'open' ? 'open' : 'name'),
  }

  return (
    <section>
      <div className="eyebrow">MY CLASS</div>
      <div className="tool-heading">
        <h2>우리 반 학생</h2>
        <span className="muted">{students.length}명</span>
      </div>
      <InviteCard />
      <div className="search-row">
      <input
        className="notice-input student-search"
        type="search"
        placeholder="이름 검색"
        aria-label="학생 이름 검색"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <SortSelect control={sortControl} />
      </div>
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
                    {s.parent_name ? `학부모 ${s.parent_name}` : '학부모 미연결'}
                    {' · '}
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
  const mine = conversations.filter((c) => student && c.student_id === student.id)
  const { show, setShow, shown, openCount, closedCount, sortControl } = useStatusFilter(mine) // 대화 중 / 종료된 대화
  // 「삭제한 대화」에서 연 대화 (읽기 전용). 브라우저 뒤로 가기로 학생 화면에 돌아오도록 기록(history state)에 둔다
  const location = useLocation()
  const viewingDeleted = (location.state as { viewDeleted?: Conversation } | null)?.viewDeleted ?? null
  if (viewingDeleted) {
    return (
      <TeacherThread
        key={viewingDeleted.id}
        conversation={viewingDeleted}
        deleted
        onBack={() => navigate(-1)}
        onLeave={(message) => {
          navigate(-1)
          setError(message)
        }}
        onDeleted={() => navigate(-1)}
      />
    )
  }
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
  const openChat = (conversationId: number) => navigate(`/teacher?chat=${conversationId}`)

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
          <small>{student.parent_name ? `학부모 ${student.parent_name}` : '연결된 학부모 없음'}</small>
        </div>
      </div>
      <div className="section-title">
        <h3>메모</h3>
      </div>
      <StudentMemoBox key={student.id} studentId={student.id} studentName={student.name} />

      <div className="section-title">
        <h3>학부모와의 대화</h3>
        {student.parent_name && (
          <button type="button" className="manual-add" onClick={() => void start()} disabled={busy}>
            ＋ 학부모와 새 대화
          </button>
        )}
      </div>
      {error && <p className="alert" role="alert">{error}</p>}
      {!student.parent_name && (
        <p className="sub">
          아직 연결된 학부모가 없어요. 학부모가 반 초대 코드와 「{student.name}」 이름으로 들어오면 대화할 수 있어요.
        </p>
      )}
      {mine.length === 0 && student.parent_name && <div className="empty">학부모와 나눈 대화가 없어요</div>}
      {mine.length > 0 && (
        <StatusFilter show={show} setShow={setShow} openCount={openCount} closedCount={closedCount} shownCount={shown.length} sort={sortControl} />
      )}
      <ConversationList conversations={shown} onSelect={openChat} />
      <DeletedConversations key={student.id} studentId={student.id} onOpen={(c) => navigate('.', { state: { viewDeleted: c } })} />
    </section>
  )
}

// 학생 화면 맨 아래 「삭제한 대화 보기」: 내 목록에서 지운 이 학생의 대화. 누르면 읽기 전용으로 연다 (onOpen)
function DeletedConversations({ studentId, onOpen }: { studentId: number; onOpen: (c: Conversation) => void }) {
  const [open, setOpen] = useState(false)
  const [rows, setRows] = useState<Conversation[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      const all = await listConversations(true)
      setRows(all.filter((c) => c.student_id === studentId))
    } catch (e) {
      setError(e instanceof Error ? e.message : '불러오지 못했습니다')
    }
  }, [studentId])

  return (
    <div className="deleted-conversations">
      <button
        type="button"
        className="outline"
        aria-expanded={open}
        onClick={() => {
          if (!open) void load()
          setOpen((o) => !o)
        }}
      >
        {open ? '삭제한 대화 닫기' : '삭제한 대화 보기'}
      </button>
      {open && (
        <>
          {error && <p className="alert" role="alert">{error}</p>}
          {rows === null && !error && <p className="loading">불러오는 중</p>}
          {rows !== null && rows.length === 0 && <div className="empty">삭제한 대화가 없어요</div>}
          {rows !== null && rows.length > 0 && (
            <ConversationList
              conversations={sortConversations(rows)}
              onSelect={(cid) => {
                const c = rows.find((r) => r.id === cid)
                if (c) onOpen(c)
              }}
            />
          )}
        </>
      )}
    </div>
  )
}

// 학생 탭: 메모 칸을 늘 펼쳐 둔다
function StudentMemoBox({ studentId, studentName }: { studentId: number; studentName: string }) {
  const memo = useStudentMemo(studentId)
  return <MemoPanel memo={memo} studentName={studentName} />
}
