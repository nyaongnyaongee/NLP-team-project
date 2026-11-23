import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import QRCode from 'qrcode'
import { getInviteCode } from '../../api/students'
import { useResource } from '../chat/useResource'

const NONE = { code: '' }

// 교사 「학생」 탭 위: 반 초대 코드 + QR. 학부모는 QR 로 「초대 코드로 시작하기」 화면을 열고 코드를 적는다.
// QR 에는 코드를 넣지 않는다 (코드는 따로 불러 주거나 화면에 띄운다). 주소는 지금 이 화면의 주소 그대로라,
// 폰에서 열리는 주소(시연 공개 주소)로 들어와 있어야 폰이 열 수 있다.
export default function InviteCard() {
  const load = useCallback(() => getInviteCode(), [])
  const { data, error } = useResource(load, NONE)
  const [open, setOpen] = useState(false)
  const [qr, setQr] = useState<string | null>(null)
  const joinUrl = `${window.location.origin}/join`

  useEffect(() => {
    if (!open) return
    let alive = true
    QRCode.toDataURL(joinUrl, { margin: 1, width: 480 })
      .then((url) => alive && setQr(url))
      .catch(() => alive && setQr(null))
    return () => {
      alive = false
    }
  }, [open, joinUrl])

  if (error) return <p className="alert" role="alert">{error}</p>
  if (!data.code) return null
  return (
    <section className="invite-card">
      <div className="invite-row">
        <div>
          <small>학부모 초대 코드</small>
          <b className="invite-code">{data.code}</b>
        </div>
        <button type="button" className="notice-create" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
          {open ? 'QR 닫기' : 'QR 보기'}
        </button>
      </div>
      {open && (
        <div className="invite-qr">
          {qr ? <img src={qr} alt={`${joinUrl} 로 가는 QR 코드`} /> : <p className="loading">QR 만드는 중</p>}
          <small>{joinUrl}</small>
          <p className="sub">QR 로 열고 초대 코드 · 자녀 이름 · 보호자 이름을 적으면 바로 연결돼요</p>
          <Link to="/teacher/cards" className="link-button">🎭 시연 QR 보기 ›</Link>
        </div>
      )}
    </section>
  )
}
