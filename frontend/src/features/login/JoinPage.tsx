import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { HOME_PATH } from '../../auth/roles'
import AppShell from '../../components/AppShell'
import ScenarioCard from '../demo/ScenarioCard'
import { findScenario, saveScenarioId } from '../demo/scenarios'

// 초대 코드로 시작하기 (시연: 가입 없이). QR 로 이 화면을 열고, 선생님께 받은 코드 + 자녀 이름 + 보호자 이름을 적으면
// 학부모 계정이 생기고 자녀가 담임 반에 이어져 바로 학부모 화면으로 간다. 주소에 ?code= 가 있으면 코드를 채워 둔다.
// 시연: ?card=<id> 가 있으면 역할 카드를 보여 주고 이 폰에 기억해 둔다. 이미 들어와 있어도 입장 화면을 보여 줘서
// 새 학부모로 들어오거나(노트북 한 대로 시험할 때 새 탭 = 새 학부모), 「지금 계정으로 계속하기」로 카드만 바꿀 수 있다.
export default function JoinPage() {
  const { session, join } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const scenario = findScenario(params.get('card'))
  // 카드 QR 로 들어오면 이 폰에 카드를 기억한다 (처음 그릴 때 한 번)
  useState(() => {
    if (scenario) saveScenarioId(scenario.id)
  })
  const [code, setCode] = useState(() => params.get('code') ?? '')
  const [studentName, setStudentName] = useState('')
  const [parentName, setParentName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [entered, setEntered] = useState(false) // 이 화면에서 방금 들어왔으면 학부모 화면으로

  if (session && (!scenario || entered)) return <Navigate to={HOME_PATH[session.role]} replace />
  const current = session?.role === 'parent' ? session : null // 이 탭에 이미 있는 학부모 (카드만 바꿔 계속할 수 있음)

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
      setEntered(true) // session 이 생겨 위의 Navigate 가 학부모 화면으로 보낸다.
    } catch (e) {
      setError(e instanceof Error ? e.message : '들어가지 못했습니다')
      setBusy(false)
    }
  }

  return (
    <AppShell title="초대 코드로 시작하기">
      {scenario ? (
        <>
          <ScenarioCard scenario={scenario} compact />
          {current && (
            <button type="button" className="primary scenario-continue" onClick={() => navigate('/parent', { replace: true })}>
              {current.name} 학부모로 계속하기
            </button>
          )}
          <p className="sub">
            {current ? '또는 새 학부모로 입장하세요. ' : ''}당신과 자녀의 이름을 정하고 입장하세요. 아무 이름이나 괜찮아요.
          </p>
        </>
      ) : (
        <>
          <div className="eyebrow">FOR PARENTS</div>
          <h2>초대 코드로<br />선생님과 연결하기</h2>
          <p className="sub">담임 선생님께 받은 코드를 적어 주세요</p>
        </>
      )}
      <form className="manual-form login-form" onSubmit={onSubmit} noValidate>
        {!(scenario && params.get('code')) && (
          <>
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
          </>
        )}
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
          {busy ? (<><span className="spinner" />연결하는 중</>) : scenario ? '입장하기 🎭' : '시작하기'}
        </button>
      </form>
      <p className="join-link">
        계정이 있으신가요? <Link to="/login">로그인</Link>
      </p>
    </AppShell>
  )
}
