import { useMemo } from 'react'
import { Link, Route, Routes, useParams } from 'react-router-dom'
import { listNotices } from '../../api/notices'
import type { Notice } from '../../api/types'
import { useNoticeSync } from '../../realtime/useNoticeSync'
import { formatTime } from '../chat/formatTime'
import { useResource } from '../chat/useResource'
import NoticeView from './NoticeView'
import { editedAfterSend } from './noticeEdited'

const NO_NOTICES: Notice[] = []
const BASE = '/parent/notices'

// 학부모 "공지사항" 탭: 게시된 공지의 목록과 상세.
// 목록(본문 포함)을 한 번 읽어 상세도 거기서 찾는다. 게시·수정·삭제 알림이 오면 목록을 다시 읽는다.
export default function ParentNotices() {
  const { data, loaded, error, refresh } = useResource(listNotices, NO_NOTICES)
  useNoticeSync(refresh)
  const loading = !loaded && error === null
  // 서버가 게시된 것만 주지만, 초안이 학부모 화면에 나오는 일이 없도록 한 번 더 거른다.
  const notices = useMemo(() => data.filter((n) => n.status === 'sent'), [data])

  return (
    <section>
      <Routes>
        <Route
          index
          element={
            <div>
              <div className="eyebrow">CLASS NOTICE BOARD</div>
              <div className="notice-heading">
                <h2>우리 반 공지사항</h2>
              </div>
              <p className="sub">{notices.length}개</p>
              {loading && <p className="loading">불러오는 중</p>}
              {error && <p className="alert" role="alert">{error}</p>}
              {!loading && !error && notices.length === 0 && <div className="empty">게시된 공지가 없어요</div>}
              {notices.map((n) => (
                <article key={n.id} className="notice-card">
                  <Link className="notice-link" to={`${BASE}/${n.id}`}>
                    <span className="tag">학급 공지</span>
                    <h3>{n.title}</h3>
                    <p>{n.body}</p>
                    {n.sent_at && <small>{formatTime(n.sent_at)}{editedAfterSend(n) && ' · 수정됨'}</small>}
                  </Link>
                  <div className="notice-foot">
                    <Link className="notice-detail" to={`${BASE}/${n.id}`}>
                      자세히 보기 →
                    </Link>
                  </div>
                </article>
              ))}
            </div>
          }
        />
        <Route path=":id" element={<ParentNoticeDetail notices={notices} loading={loading} />} />
      </Routes>
    </section>
  )
}

function ParentNoticeDetail({ notices, loading }: { notices: Notice[]; loading: boolean }) {
  const { id } = useParams()
  const notice = notices.find((n) => String(n.id) === id) ?? null
  if (loading) return <p className="loading">불러오는 중</p>
  return (
    <div>
      <Link className="back" to={BASE}>
        ‹ 공지사항
      </Link>
      {notice ? <NoticeView notice={notice} /> : <p className="alert" role="alert">찾을 수 없습니다</p>}
    </div>
  )
}
