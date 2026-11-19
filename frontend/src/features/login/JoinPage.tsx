import { useState, type FormEvent } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { HOME_PATH } from '../../auth/roles'
import AppShell from '../../components/AppShell'

// 초대 코드로 시작하기 (시연: 가입 없이). QR 로 이 화면을 열고, 선생님께 받은 코드 + 자녀 이름 + 보호자 이름을 적으면
// 학부모 계정이 생기고 자녀가 담임 반에 이어져 바로 학부모 화면으로 간다. 주소에 ?code= 가 있으면 코드를 채워 둔다.
export default function JoinPage() {
  const { session, join } = useAuth()
  const [params] = useSearchParams()
  const [code, setCode] = useState(() => params.get('code') ?? '')
  const [studentName, setStudentName] = useState('')
  const [parentName, setParentName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (session) return <Navigate to={HOME_PATH[session.role]} replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (busy) return
    if (code.trim() === '' || studentName.trim() === '' || parentName.trim() === '') {
      setError('초대 코드, 자녀 이름, 보호자 이름을 모두 적어 주세요')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await join(code.trim(), studentName.trim(), parentName.trim())
      // 성공하면 session 이 생겨 위의 Navigate 가 학부모 화면으로 보낸다.
    } catch (e) {
      setError(e instanceof Error ? e.message : '들어가지 못했습니다')
      setBusy(false)
    }
  }

  return (
    <AppShell title="초대 코드로 시작하기">
      <div className="eyebrow">FOR PARENTS</div>
      <h2>초대 코드로<br />선생님과 연결하기</h2>
      <p className="sub">담임 선생님께 받은 코드를 적어 주세요</p>
      <form className="manual-form login-form" onSubmit={onSubmit} noValidate>
        <label className="editor-label" htmlFor="join-code">초대 코드</label>
        <input
          id="join-code"
          className="invite-input"
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          placeholder="선생님께 받은 코드"
          autoComplete="off"
          autoCapitalize="characters"
          spellCheck={false}
        />
        <label className="editor-label" htmlFor="join-student">자녀 이름</label>
        <input
          id="join-student"
          value={studentName}
          onChange={(e) => setStudentName(e.target.value)}
          placeholder="예: 김하늘"
          autoComplete="off"
        />
        <label className="editor-label" htmlFor="join-parent">보호자 이름</label>
        <input
          id="join-parent"
          value={parentName}
          onChange={(e) => setParentName(e.target.value)}
          placeholder="예: 김보람"
          autoComplete="name"
        />
        {error && <p className="alert" role="alert">{error}</p>}
        <button type="submit" className="primary" disabled={busy}>
          {busy ? (<><span className="spinner" />연결하는 중</>) : '시작하기'}
        </button>
      </form>
      <p className="join-link">
        계정이 있으신가요? <Link to="/login">로그인</Link>
      </p>
    </AppShell>
  )
}
