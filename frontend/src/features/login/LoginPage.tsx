import { useState, type FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { ApiError } from '../../api/client'
import { useAuth } from '../../auth/AuthContext'
import { HOME_PATH } from '../../auth/roles'
import AppShell from '../../components/AppShell'

const BAD_CREDENTIALS = '아이디 또는 비밀번호가 틀렸습니다'

export default function LoginPage() {
  const { session, login } = useAuth()
  const [loginId, setLoginId] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // 이미 로그인했으면 자기 시작 화면으로
  if (session) return <Navigate to={HOME_PATH[session.role]} replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (busy) return
    if (loginId.trim() === '' || password === '') {
      setError('아이디와 비밀번호를 입력해 주세요') // 비어 있으면 요청을 보내지 않는다
      return
    }
    setBusy(true)
    setError(null)
    try {
      await login(loginId.trim(), password)
      // 성공하면 session 이 생겨 위의 Navigate 가 이동시킨다.
    } catch (e) {
      // 어느 쪽이 틀렸는지 알려 주지 않는다. 연결 문제 등은 해당 문장을 그대로 보여 준다.
      if (e instanceof ApiError && e.status !== 401) setError(e.message)
      else setError(BAD_CREDENTIALS)
      setBusy(false)
    }
  }

  return (
    <AppShell title="이음 로그인">
      <div className="eyebrow">SCHOOL COMMUNICATION</div>
      <h2>소통은 부드럽게,<br />업무는 간편하게</h2>
      <p className="sub">학교와 가정을 잇는 소통</p>
      <form className="manual-form login-form" onSubmit={onSubmit} noValidate>
        <label className="editor-label" htmlFor="login-id">아이디</label>
        <input
          id="login-id"
          value={loginId}
          onChange={(e) => setLoginId(e.target.value)}
          autoComplete="username"
          autoCapitalize="none"
        />
        <label className="editor-label" htmlFor="login-password">비밀번호</label>
        <input
          id="login-password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
        />
        {error && <p className="alert" role="alert">{error}</p>}
        <button type="submit" className="primary" disabled={busy}>
          {busy ? (<><span className="spinner" />로그인 중</>) : '로그인'}
        </button>
      </form>
    </AppShell>
  )
}
