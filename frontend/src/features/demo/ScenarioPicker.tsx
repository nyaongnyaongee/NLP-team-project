import { SCENARIOS } from './scenarios'

// 시연 QR 로 들어온 학부모가 처음 보는 화면: 상황 6개 중 하나를 고른다. 상황은 고른 뒤에 펼쳐진다 (궁금하게).
export default function ScenarioPicker({ onPick }: { onPick: (id: string) => void }) {
  return (
    <section className="scenario-picker" aria-label="상황 고르기">
      <p className="scenario-intro">🎭 오늘 당신은 「그 학부모」입니다. 실제 선생님들이 겪은 일이에요.</p>
      <h3>어떤 학부모가 되어 볼까요?</h3>
      <div className="scenario-choices">
        {SCENARIOS.map((s) => (
          <button key={s.id} type="button" className="scenario-choice" onClick={() => onPick(s.id)}>
            <span className="scenario-emoji" aria-hidden="true">{s.emoji}</span>
            <b>{s.title}</b>
            <small>{s.heat}</small>
          </button>
        ))}
      </div>
    </section>
  )
}
