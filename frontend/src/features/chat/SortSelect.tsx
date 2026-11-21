import { useEffect, useRef, useState } from 'react'

export type SortOption = { value: string; label: string }

export type SortControl = {
  options: SortOption[]
  value: string
  desc: boolean // true = 내림차순(↓), false = 오름차순(↑)
  onPick: (value: string) => void // 다른 항목이면 그 항목으로, 지금 항목을 한 번 더 누르면 방향을 바꾼다
}

// 작은 정렬 메뉴 (대화 목록 · 학생 목록 공용). 고른 항목 오른쪽에 방향 화살표가 붙고, 그 항목을 한 번 더 누르면 방향이 바뀐다.
// 방향을 바꿀 때는 메뉴를 열어 둔 채 화살표만 뒤집는다. 다른 항목을 고르면 닫힌다.
export default function SortSelect({ control }: { control: SortControl }) {
  const [open, setOpen] = useState(false)
  const wrapRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDown = (e: PointerEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('pointerdown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const current = control.options.find((o) => o.value === control.value) ?? control.options[0]
  const arrow = control.desc ? '↓' : '↑'
  const order = control.desc ? '내림차순' : '오름차순'
  return (
    <div className="sort-menu" ref={wrapRef}>
      <button
        type="button"
        className="sort-trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`정렬: ${current.label}, ${order}`}
        onClick={() => setOpen((o) => !o)}
      >
        <span>{current.label}</span>
        <span className="sort-arrow" aria-hidden="true">{arrow}</span>
      </button>
      {open && (
        <ul className="sort-list" role="listbox" aria-label="정렬 기준">
          {control.options.map((o) => {
            const active = o.value === control.value
            return (
              <li key={o.value} role="presentation">
                <button
                  type="button"
                  role="option"
                  aria-selected={active}
                  className={active ? 'active' : ''}
                  onClick={() => {
                    control.onPick(o.value)
                    if (!active) setOpen(false)
                  }}
                >
                  <span>{o.label}</span>
                  {active && <span className="sort-arrow" aria-label={order}>{arrow}</span>}
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
