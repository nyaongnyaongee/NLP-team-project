import { useState } from 'react'
import type { Scenario } from './scenarios'

// 학부모 「메시지 작성」 위에 뜨는 역할 카드. compact 면 입장 화면용 짧은 모양 (상황까지만).
export default function ScenarioCard({ scenario, compact = false, onClose }: {
  scenario: Scenario
  compact?: boolean
  onClose?: () => void
}) {
  const [done, setDone] = useState<boolean[]>(() => scenario.missions.map(() => false))
  const [showHint, setShowHint] = useState(false)

  return (
    <section className={`scenario-card${compact ? ' compact' : ''}`} aria-label={`역할 카드: ${scenario.title}`}>
      <p className="scenario-intro">🎭 오늘 당신은 「그 학부모」입니다. 실제 선생님들이 겪은 일이에요.</p>
      <div className="scenario-head">
        <span className="scenario-emoji" aria-hidden="true">{scenario.emoji}</span>
        <div>
          <h3>{scenario.title}</h3>
          <small>분노 게이지 {scenario.heat}</small>
        </div>
        {onClose && (
          <button type="button" className="link-button scenario-close" onClick={onClose}>
            카드 닫기
          </button>
        )}
      </div>
      {scenario.situation.map((line) => (
        <p key={line} className="scenario-situation">{line}</p>
      ))}
      {!compact && (
        <>
          <ul className="scenario-missions">
            {scenario.missions.map((m, i) => (
              <li key={m}>
                <label>
                  <input
                    type="checkbox"
                    checked={done[i]}
                    onChange={() => setDone((old) => old.map((v, j) => (j === i ? !v : v)))}
                  />
                  <span>{m}</span>
                </label>
              </li>
            ))}
          </ul>
          {scenario.note && <p className="scenario-note">{scenario.note}</p>}
          <p className="scenario-rule">참지 말고 보내세요. <b>욕설 · 반말 대환영.</b> 선생님 화면에 어떻게 도착하는지는… 보내 보면 압니다 🔓</p>
          <button type="button" className="link-button" onClick={() => setShowHint((v) => !v)} aria-expanded={showHint}>
            {showHint ? '예시 숨기기' : '막히면? 예시 보기'}
          </button>
          {showHint && <p className="scenario-hint">「{scenario.hint}」</p>}
        </>
      )}
    </section>
  )
}
