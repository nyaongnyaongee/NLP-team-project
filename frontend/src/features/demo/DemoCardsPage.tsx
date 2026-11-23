import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import QRCode from 'qrcode'
import { getInviteCode } from '../../api/students'
import { useResource } from '../chat/useResource'
import { SCENARIOS } from './scenarios'

const NONE = { code: '' }

// 교사용: 시연 역할 카드 6장의 QR 포스터. 카드마다 /join?code=<반 코드>&card=<id>.
// 포스터에는 이모지 · 제목 · 분노 게이지만 (상황은 찍어야 보인다). 인쇄하면 한 장에 한 카드.
// 주소는 지금 이 화면의 주소 그대로라, 폰이 열 수 있는 주소(시연 공개 주소)로 들어와 있어야 한다.
export default function DemoCardsPage() {
  const load = useCallback(() => getInviteCode(), [])
  const { data, error } = useResource(load, NONE)
  const [qrs, setQrs] = useState<Record<string, string>>({})
  const origin = window.location.origin

  useEffect(() => {
    if (!data.code) return
    let alive = true
    Promise.all(
      SCENARIOS.map(async (s) => {
        const url = `${origin}/join?code=${encodeURIComponent(data.code)}&card=${s.id}`
        return [s.id, await QRCode.toDataURL(url, { margin: 1, width: 560 })] as const
      }),
    )
      .then((pairs) => alive && setQrs(Object.fromEntries(pairs)))
      .catch(() => alive && setQrs({}))
    return () => {
      alive = false
    }
  }, [data.code, origin])

  return (
    <section className="demo-cards-page">
      <div className="demo-cards-bar">
        <Link to="/teacher/students" className="link-button">‹ 학생 탭으로</Link>
        <button type="button" className="notice-create" onClick={() => window.print()}>인쇄</button>
      </div>
      <h2>시연 역할 카드</h2>
      <p className="sub">관객이 마음에 드는 카드의 QR 을 찍고, 자기 이름 · 자녀 이름을 적어 들어옵니다. 같은 폰에서 다른 QR 을 찍으면 카드만 바뀝니다.</p>
      {error && <p className="alert" role="alert">{error}</p>}
      <div className="demo-posters">
        {SCENARIOS.map((s) => (
          <article key={s.id} className="demo-poster">
            <span className="demo-poster-emoji" aria-hidden="true">{s.emoji}</span>
            <h3>{s.title}</h3>
            <p className="demo-poster-heat">{s.heat}</p>
            {qrs[s.id] ? <img src={qrs[s.id]} alt={`${s.title} 카드 QR`} /> : <p className="loading">QR 만드는 중</p>}
            <small>찍어서 「그 학부모」가 되어 보세요</small>
          </article>
        ))}
      </div>
    </section>
  )
}
