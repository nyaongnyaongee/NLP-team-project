import { useNavigate } from 'react-router-dom'
import { SCENARIOS, heatLabel, saveScenarioId } from './scenarios'

// 시연 QR 로 들어온 학부모의 첫 화면 (/parent/pick): 상황 카드(순한맛부터) 중 하나를 고르면 메시지 작성 화면으로 간다.
// 상황 내용은 고른 뒤에 펼쳐진다 (궁금하게). 메시지 작성 화면의 「다른 상황 고르기」로 다시 온다.
export default function ScenarioPicker() {
  const navigate = useNavigate()

  function pick(id: string) {
    saveScenarioId(id)
    navigate('/parent', { replace: true })
  }

  return (
    <section className="scenario-picker" aria-label="상황 고르기">
      <p className="scenario-intro">🎭 오늘 당신은 「그 학부모」입니다</p>
      <h2>어떤 학부모가 되어 볼까요?</h2>
      <p className="sub">모두 실제 선생님들이 겪은 일이에요. 순한맛부터 지옥맛까지, 하나를 고르면 상황이 펼쳐집니다.</p>
      <div className="scenario-choices">
        {SCENARIOS.map((s) => {
          const { fire, level } = heatLabel(s)
          return (
            <button key={s.id} type="button" className={`scenario-choice heat-${s.heatText ? 'ramp' : s.heat}`} onClick={() => pick(s.id)}>
              <span className="scenario-level">{level}</span>
              <span className="scenario-emoji" aria-hidden="true">{s.emoji}</span>
              <b>{s.title}</b>
              <small>{fire}</small>
            </button>
          )
        })}
      </div>
    </section>
  )
}
