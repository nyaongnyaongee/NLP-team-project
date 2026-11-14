import { useState } from 'react'
import { Link, Route, Routes, useLocation, useNavigate, useParams } from 'react-router-dom'
import { listNotices } from '../../api/notices'
import type { Notice } from '../../api/types'
import { useResource } from '../chat/useResource'
import NoticeEditor from './NoticeEditor'
import TeacherNoticeRow from './TeacherNoticeRow'

const NO_NOTICES: Notice[] = []
const BASE = '/teacher/notices'

// 교사 "공지사항" 탭: 목록(초안과 게시를 구분), 새 공지(/new), 공지 보기·수정(/:id).
// 목록은 여기서 한 번 읽어 하위 화면이 나눠 쓴다 (본문까지 들어 있다).
export default function TeacherNotices() {
  const { data, setData, loaded, error, refresh } = useResource(listNotices, NO_NOTICES)
  const navigate = useNavigate()
  const loading = !loaded && error === null

  const upsert = (n: Notice) =>
    setData((prev) => (prev.some((p) => p.id === n.id) ? prev.map((p) => (p.id === n.id ? n : p)) : [n, ...prev]))
  const remove = (id: number) => setData((prev) => prev.filter((p) => p.id !== id))
  const onConflict = () => void refresh() // 게시 여부가 서버와 어긋났으니 다시 읽는다

  // 수정 화면에서 409 를 받으면 목록을 다시 읽는다.
  // 서버의 detail 문장이 사라지지 않도록 그 주소에 머무는 동안 계속 보여 준다 (명세 S6).
  const location = useLocation()
  const [conflict, setConflict] = useState<{ message: string; path: string } | null>(null)
  const onEditorConflict = (message: string) => {
    setConflict({ message, path: location.pathname })
    void refresh()
  }

  return (
    <section>
      {conflict && conflict.path === location.pathname && <p className="alert" role="alert">{conflict.message}</p>}
      <Routes>
        <Route
          index
          element={
            <div>
              <div className="eyebrow">CLASS NOTICE BOARD</div>
              <div className="notice-heading">
                <h2>우리 반 공지사항</h2>
                <Link className="notice-create" to={`${BASE}/new`}>
                  ＋ 공지 작성
                </Link>
              </div>
              <p className="sub">{data.length}개</p>
              {loading && <p className="loading">불러오는 중</p>}
              {error && <p className="alert" role="alert">{error}</p>}
              {!loading && !error && data.length === 0 && <div className="empty">작성한 공지가 없어요</div>}
              {data.map((n) => (
                <TeacherNoticeRow
                  key={n.id}
                  notice={n}
                  onChanged={upsert}
                  onRemoved={remove}
                  onConflict={onConflict}
                />
              ))}
            </div>
          }
        />
        <Route
          path="new"
          element={
            <NoticeEditor
              notice={null}
              onSaved={(n) => {
                upsert(n)
                navigate(BASE)
              }}
              onCancel={() => navigate(BASE)}
              onConflict={onEditorConflict}
            />
          }
        />
        <Route
          path=":id"
          element={
            <NoticeDetail
              notices={data}
              loading={loading}
              onSaved={(n) => {
                upsert(n)
                navigate(BASE)
              }}
              onConflict={onEditorConflict}
            />
          }
        />
      </Routes>
    </section>
  )
}

// 공지 하나: 초안도 게시된 공지도 수정 화면 (게시된 공지는 저장하면 학부모 화면에 바로 반영).
function NoticeDetail({
  notices,
  loading,
  onSaved,
  onConflict,
}: {
  notices: Notice[]
  loading: boolean
  onSaved: (n: Notice) => void
  onConflict: (message: string) => void
}) {
  const { id } = useParams()
  const navigate = useNavigate()
  const notice = notices.find((n) => String(n.id) === id) ?? null

  if (loading) return <p className="loading">불러오는 중</p>
  if (!notice) {
    return (
      <div>
        <Link className="back" to={BASE}>
          ‹ 공지사항
        </Link>
        <p className="alert" role="alert">찾을 수 없습니다</p>
      </div>
    )
  }
  return (
    <NoticeEditor
      key={notice.id}
      notice={notice}
      onSaved={onSaved}
      onCancel={() => navigate(BASE)}
      onConflict={onConflict}
    />
  )
}
