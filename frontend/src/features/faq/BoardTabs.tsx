import { useNavigate } from 'react-router-dom'

// 공지사항 탭 위의 「공지 / 자주 묻는 질문」 전환 (교사 · 학부모 공용). base = '/teacher/notices' 또는 '/parent/notices'
export default function BoardTabs({ base, active }: { base: string; active: 'notice' | 'faq' }) {
  const navigate = useNavigate()
  return (
    <div className="chips board-tabs" role="group" aria-label="공지사항 / 자주 묻는 질문">
      <button type="button" className={active === 'notice' ? 'active' : ''} aria-pressed={active === 'notice'} onClick={() => navigate(base)}>
        공지
      </button>
      <button type="button" className={active === 'faq' ? 'active' : ''} aria-pressed={active === 'faq'} onClick={() => navigate(`${base}/faq`)}>
        자주 묻는 질문
      </button>
    </div>
  )
}
