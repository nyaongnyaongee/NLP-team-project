import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'

const COLUMN = 64 // 오른쪽 동작 버튼 열의 너비 (px)
const COLUMN_CONFIRM = 88 // 「다시 눌러 확인」 단계의 열 너비
const OPEN_RATIO = 0.4 // 열 너비의 이만큼 넘게 밀고 놓으면 열린다
const FLICK = 0.3 // px/ms. 이보다 빠르게 튕기면 방향대로 열리거나 닫힌다
const OVERSHOOT_MAX = 24 // 열 너비보다 더 끌 수 있는 최대 거리 (고무줄)
const OVERSHOOT_RESIST = 0.3
const DRAG_SLOP = 8 // 이만큼 움직이기 전에는 끌기로 보지 않는다
const SAMPLE_MS = 100 // 놓을 때 속도를 재는 최근 구간

export type SwipeAction = {
  key: string
  label: string // 「종료」 「삭제」
  ariaLabel: string // 「박서연 (박지민의 학부모) 대화 종료」
  danger?: boolean
  onConfirm: () => void // 「다시 눌러 확인」 단계에서 한 번 더 눌렀을 때 실행
}

// 목록 줄: 왼쪽으로 밀거나(스와이프) 줄 안의 「⋯」 를 누르면 줄이 왼쪽으로 밀리며 오른쪽에 동작 버튼이 세로로 나타난다.
// 두 방법은 같은 열린 상태(open)로 이어진다. children 은 줄 안의 ⋯ · ✕ 버튼이 같은 열기·닫기를 부를 수 있게 함수로 받는다.
//  - 닫기: ✕ · 줄 본문 누르기 · 줄 밖 누르기 · 목록 스크롤 · 오른쪽으로 밀기 · Esc
//  - 실행: 버튼을 한 번 누르면 「다시 눌러 확인」으로 바뀌고, 한 번 더 누르면 실행한다 (확인 창을 쓰지 않는다)
// 위아래로 스크롤하는 손짓은 그대로 두고(touch-action: pan-y), 옆으로 8px 넘게 움직였을 때만 민다. 마우스로도 끌 수 있다.
export default function SwipeRow({
  open,
  onOpenChange,
  actions,
  children,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  actions: SwipeAction[] // 위에서 아래 순서
  children: (api: { requestOpen: () => void; requestClose: () => void }) => ReactNode
}) {
  const rootRef = useRef<HTMLDivElement>(null)
  const [confirming, setConfirming] = useState<string | null>(null) // 한 번 눌러 확인을 기다리는 버튼의 key
  const [dx, setDx] = useState<number | null>(null) // 끄는 중일 때만 값이 있다
  const start = useRef<{ x: number; y: number; base: number } | null>(null)
  const samples = useRef<{ x: number; t: number }[]>([])
  const dragged = useRef(false) // 끌기였으면 뒤따르는 click 을 막는다
  // 열기·닫기 뒤에 포커스를 옮길 곳: ⋯ 로 열었으면 첫 동작 버튼, ✕ · Esc 로 닫았으면 ⋯ (스와이프 · 바깥 누르기 · 스크롤은 포커스를 옮기지 않는다)
  const [focusRequest, setFocusRequest] = useState<'first' | 'toggle' | null>(null)
  const onOpenChangeRef = useRef(onOpenChange)
  useEffect(() => {
    onOpenChangeRef.current = onOpenChange
  })

  if (!open && confirming !== null) setConfirming(null) // 닫히면 확인 단계도 처음으로

  const width = confirming !== null ? COLUMN_CONFIRM : COLUMN
  const offset = dx ?? (open ? -width : 0)
  const reveal = Math.min(1, Math.max(0, (Math.abs(offset) - 12) / (COLUMN - 12))) // 미는 만큼 글자가 진해진다

  const requestOpen = () => {
    setFocusRequest('first')
    onOpenChange(true)
  }
  const requestClose = () => {
    setFocusRequest('toggle')
    onOpenChange(false)
  }

  useEffect(() => {
    const root = rootRef.current
    if (!root || focusRequest === null) return
    if (focusRequest === 'first' && open) root.querySelector<HTMLElement>('.swipe-action')?.focus({ preventScroll: true })
    else if (focusRequest === 'toggle' && !open) root.querySelector<HTMLElement>('[data-swipe-toggle]')?.focus({ preventScroll: true })
    else return // 열림 상태가 아직 따라오지 않았다
    // 포커스를 옮겼으니 요청을 비운다 (DOM 포커스라는 바깥 시스템과 맞추는 effect)
    // oxlint-disable-next-line react/set-state-in-effect
    setFocusRequest(null)
  }, [open, focusRequest])

  // 열려 있는 동안: 줄 밖 누르기 · 목록 스크롤 · Esc 로 닫는다
  useEffect(() => {
    if (!open) return
    const root = rootRef.current
    const scroller = root?.closest('.content')
    const close = () => onOpenChangeRef.current(false)
    const onDown = (e: PointerEvent) => {
      if (!root?.contains(e.target as Node)) close()
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      setFocusRequest('toggle')
      close()
    }
    document.addEventListener('pointerdown', onDown)
    document.addEventListener('keydown', onKey)
    scroller?.addEventListener('scroll', close, { passive: true })
    return () => {
      document.removeEventListener('pointerdown', onDown)
      document.removeEventListener('keydown', onKey)
      scroller?.removeEventListener('scroll', close)
    }
  }, [open])

  const end = () => {
    const s = start.current
    start.current = null
    if (!s || dx === null) {
      setDx(null)
      return
    }
    const pts = samples.current
    let v = 0 // 놓기 직전 속도 (px/ms, 왼쪽이 음수)
    if (pts.length >= 2) {
      const a = pts[0]
      const b = pts[pts.length - 1]
      if (b.t > a.t) v = (b.x - a.x) / (b.t - a.t)
    }
    samples.current = []
    onOpenChange(v < -FLICK ? true : v > FLICK ? false : Math.abs(dx) > width * OPEN_RATIO)
    setDx(null)
  }

  const press = (a: SwipeAction, button: HTMLButtonElement) => {
    if (confirming !== a.key) {
      setConfirming(a.key)
      button.focus({ preventScroll: true })
      return
    }
    a.onConfirm()
    onOpenChange(false)
  }

  const reduceMotion = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true
  return (
    <div
      ref={rootRef}
      className={`swipe${open || dx !== null ? ' active' : ''}${confirming !== null ? ' confirming' : ''}${dx === null ? ' settle' : ''}`}
      style={{ '--reveal': reveal } as CSSProperties}
      onPointerDown={(e) => {
        if (e.button !== 0) return
        start.current = { x: e.clientX, y: e.clientY, base: open ? -width : 0 }
        samples.current = [{ x: e.clientX, t: e.timeStamp }]
        dragged.current = false
      }}
      onPointerMove={(e) => {
        const s = start.current
        if (!s) return
        const mx = e.clientX - s.x
        const my = e.clientY - s.y
        if (!dragged.current) {
          if (Math.abs(mx) < DRAG_SLOP && Math.abs(my) < DRAG_SLOP) return
          if (Math.abs(my) > Math.abs(mx)) {
            start.current = null // 세로 스크롤이었다
            return
          }
          dragged.current = true
          e.currentTarget.setPointerCapture(e.pointerId)
        }
        const raw = s.base + mx
        // 오른쪽으로는 더 밀리지 않고, 열 너비를 넘어 왼쪽으로는 고무줄처럼 조금만 따라온다
        const next = raw > 0 ? 0 : raw < -width ? -width - Math.min((-width - raw) * OVERSHOOT_RESIST, OVERSHOOT_MAX) : raw
        samples.current = [...samples.current.filter((p) => e.timeStamp - p.t <= SAMPLE_MS), { x: e.clientX, t: e.timeStamp }]
        setDx(next)
      }}
      onPointerUp={end}
      onPointerCancel={end}
      onClickCapture={(e) => {
        if (dragged.current) {
          dragged.current = false
          e.preventDefault()
          e.stopPropagation()
        } else if (open) {
          const target = e.target as HTMLElement
          if (!target.closest('.swipe-actions') && !target.closest('[data-swipe-toggle]')) {
            e.preventDefault() // 열린 줄의 본문을 누르면 닫히기만 한다 (대화가 열리지 않게)
            e.stopPropagation()
            onOpenChange(false)
          }
        }
      }}
    >
      <div className="swipe-actions" style={{ width, transition: reduceMotion ? 'none' : undefined }} aria-hidden={!open}>
        {actions.map((a) => (
          <button
            key={a.key}
            type="button"
            className={`swipe-action${a.danger ? ' danger' : ''}${confirming === a.key ? ' confirm' : ''}`}
            onClick={(e) => press(a, e.currentTarget)}
            tabIndex={open ? 0 : -1}
            aria-label={confirming === a.key ? `${a.ariaLabel}, 다시 눌러 확인` : a.ariaLabel}
          >
            <span className="swipe-label">
              <b>{a.label}</b>
              {confirming === a.key && <small>다시 눌러 확인</small>}
            </span>
          </button>
        ))}
      </div>
      <div
        className={`swipe-front${dx === null && !reduceMotion ? ' settle' : ''}`}
        style={{ transform: `translateX(${offset}px)` }}
      >
        {children({ requestOpen, requestClose })}
      </div>
    </div>
  )
}
