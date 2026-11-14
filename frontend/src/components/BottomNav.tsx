import type { ReactNode } from 'react'
import { useMatch, useNavigate } from 'react-router-dom'

export type NavItem = { to: string; label: string; icon: ReactNode; end?: boolean }

// 데모의 하단 탭(.bottom). 데모 CSS 가 .bottom button 에만 모양을 주므로 버튼으로 만들고, 누르면 주소를 바꾼다.
function NavButton({ item }: { item: NavItem }) {
  const match = useMatch({ path: item.to, end: item.end ?? false })
  const navigate = useNavigate()
  return (
    <button
      type="button"
      className={match ? 'active' : ''}
      aria-current={match ? 'page' : undefined}
      onClick={() => navigate(item.to)}
    >
      <span className="ico">{item.icon}</span>
      {item.label}
    </button>
  )
}

export default function BottomNav({ items, label }: { items: NavItem[]; label: string }) {
  return (
    <nav className="bottom" aria-label={label}>
      {items.map((item) => (
        <NavButton key={item.to} item={item} />
      ))}
    </nav>
  )
}
