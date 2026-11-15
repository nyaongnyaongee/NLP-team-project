import { useRef, useState, type ReactNode } from 'react'

const BUTTON = 76 // 뒤에 숨은 버튼 하나의 너비 (px)

export type SwipeAction = { label: string; ariaLabel: string; danger?: boolean; onClick: () => void }

// 폰 목록처럼 왼쪽으로 밀면 뒤에 숨은 버튼(「종료」 「삭제」 등)이 나오는 줄.
// 위아래로 스크롤하는 손짓은 그대로 두고(touch-action: pan-y), 옆으로 8px 넘게 움직였을 때만 민다.
// 민 뒤에 손을 떼면 반 넘게 밀었으면 열린 채로, 아니면 닫힌다. 열린 줄을 누르면 닫히기만 한다 (대화가 열리지 않게).
// 마우스로도 끌 수 있다 (pointer 이벤트).
export default function SwipeRow({
  open,
  onOpenChange,
  actions,
  children,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  actions: SwipeAction[] // 왼쪽부터 순서대로
  children: ReactNode
}) {
  const WIDTH = BUTTON * actions.length
  const start = useRef<{ x: number; y: number; base: number } | null>(null)
  const dragged = useRef(false) // 밀기였으면 뒤따르는 click 을 막는다
  const [dx, setDx] = useState<number | null>(null) // 미는 중일 때만 값이 있다

  const end = () => {
    if (start.current && dx !== null) onOpenChange(dx < -WIDTH / 2)
    start.current = null
    setDx(null)
  }

  const offset = dx ?? (open ? -WIDTH : 0)
  return (
    <div
      className={`swipe${open || dx !== null ? ' active' : ''}`}
      onPointerDown={(e) => {
        if (e.button !== 0) return
        start.current = { x: e.clientX, y: e.clientY, base: open ? -WIDTH : 0 }
        dragged.current = false
      }}
      onPointerMove={(e) => {
        const s = start.current
        if (!s) return
        const mx = e.clientX - s.x
        const my = e.clientY - s.y
        if (!dragged.current) {
          if (Math.abs(mx) < 8 && Math.abs(my) < 8) return
          if (Math.abs(my) > Math.abs(mx)) {
            start.current = null // 세로 스크롤이었다
            return
          }
          dragged.current = true
          e.currentTarget.setPointerCapture(e.pointerId)
        }
        setDx(Math.max(-WIDTH, Math.min(0, s.base + mx)))
      }}
      onPointerUp={end}
      onPointerCancel={end}
      onClickCapture={(e) => {
        if (dragged.current) {
          dragged.current = false
          e.preventDefault()
          e.stopPropagation()
        } else if (open && !(e.target as HTMLElement).closest('.swipe-actions')) {
          e.preventDefault()
          e.stopPropagation()
          onOpenChange(false)
        }
      }}
    >
      <div className="swipe-actions" style={{ width: WIDTH }} aria-hidden={!open}>
        {actions.map((a) => (
          <button
            key={a.label}
            type="button"
            className={`swipe-action${a.danger ? ' danger' : ''}`}
            onClick={a.onClick}
            tabIndex={open ? 0 : -1}
            aria-label={a.ariaLabel}
          >
            {a.label}
          </button>
        ))}
      </div>
      <div className={`swipe-front${dx === null ? ' settle' : ''}`} style={{ transform: `translateX(${offset}px)` }}>
        {children}
      </div>
    </div>
  )
}
