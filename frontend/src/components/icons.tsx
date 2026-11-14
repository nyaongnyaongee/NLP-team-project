// 하단 탭 아이콘: 데모(app-sage.html)의 SVG 를 그대로 옮겼다. 색은 currentColor 라 탭 상태에 따라 바뀐다.
import type { ReactNode } from 'react'

function Icon({ children }: { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  )
}

export const ChatIcon = () => (
  <Icon>
    <path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5H4l-2 2V11.5A8.5 8.5 0 0 1 10.5 3h2a8.5 8.5 0 0 1 8.5 8.5Z" />
    <path d="M7 9h9M7 13h6" />
  </Icon>
)

export const TodoIcon = () => (
  <Icon>
    <rect x="4" y="3" width="16" height="18" rx="3" />
    <path d="m8 12 3 3 5-6" />
  </Icon>
)

export const CalendarIcon = () => (
  <Icon>
    <rect x="3" y="5" width="18" height="16" rx="3" />
    <path d="M7 3v4m10-4v4M3 10h18M8 14h1m5 0h1m-7 3h1" />
  </Icon>
)

export const NoticeIcon = () => (
  <Icon>
    <path d="m4 10 14-6v16L4 14v-4Z" />
    <path d="M8 16v5h4l-2-5M21 9v6" />
  </Icon>
)
