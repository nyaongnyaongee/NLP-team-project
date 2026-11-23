import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import QRCode from 'qrcode'
import { getInviteCode } from '../../api/students'
import { useResource } from '../chat/useResource'
import { SCENARIOS } from './scenarios'

const NONE = { code: '' }

// 교사용: 시연 QR 포스터 한 장. QR = /join?code=<반 코드>&demo=1 → 이름을 적고 들어와 학부모 화면에서 상황 하나를 고른다.
// 주소는 지금 이 화면의 주소 그대로라, 폰이 열 수 있는 주소(시연 공개 주소)로 들어와 있어야 한다.
export default function DemoCardsPage() {
  const load = useCallback(() => getInviteCode(), [])
  const { data, error } = useResource(load, NONE)
  const [qr, setQr] = useState<string | null>(null)
  const url = data.code ? `${window.location.origin}/join?code=${encodeURIComponent(data.code)}&demo=1` : ''

  useEffect(() => {
    if (!url) return
    let alive = true
    QRCode.toDataURL(url, { margin: 1, width: 640 })
      .then((src) => alive && setQr(src))
      .catch(() => alive && setQr(null))
    return () => {
      alive = false
    }
  }, [url])

  return (
    <section className="demo-cards-page">
      <div className="demo-cards-bar">
        <Link to="/teacher/students" className="link-button">‹ 학생 탭으로</Link>
        <button type="button" className="notice-create" onClick={() => window.print()}>인쇄</button>
      </div>
      {error && <p className="alert" role="alert">{error}</p>}
      <article className="demo-poster demo-poster-one">
        <p className="demo-poster-kicker">🎭 오늘 당신은 「그 학부모」입니다</p>
        <h3>찍고, 화내고, 보내 보세요</h3>
        {qr ? <img src={qr} alt="시연 입장 QR 코드" /> : <p className="loading">QR 만드는 중</p>}
        <ul className="demo-poster-list">
          {SCENARIOS.map((s) => (
            <li key={s.id}>
              {s.emoji} {s.title}
            </li>
          ))}
        </ul>
        <small>실제 선생님들이 겪은 일입니다 · 욕설 · 반말 대환영</small>
        {url && <small className="demo-poster-url">{url}</small>}
      </article>
    </section>
  )
}
