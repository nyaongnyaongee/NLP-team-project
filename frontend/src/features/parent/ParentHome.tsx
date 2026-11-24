import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell from '../../components/AppShell'
import BottomNav, { type NavItem } from '../../components/BottomNav'
import { CalendarIcon, ChatIcon, NoticeIcon, PenIcon } from '../../components/icons'
import { useConversations } from '../chat/useConversations'
import ParentNotices from '../notices/ParentNotices'
import ScenarioPicker from '../demo/ScenarioPicker'
import ParentCalendar from './ParentCalendar'
import ParentCompose from './ParentCompose'
import ParentComplaintChat from './ParentComplaintChat'
import ParentConversationTab from './ParentConversationTab'

// 학부모 화면의 틀: 위에 계정 표시, 가운데에 탭 내용, 아래에 탭 메뉴 (명세 8장 주소 구조: /parent/...)
// 첫 탭 = 메시지 작성 (담임 카드 + 글쓰기), 대화 목록 탭에는 안 읽은 수
export default function ParentHome() {
  const { conversations } = useConversations()
  const unread = conversations.reduce((n, c) => n + (c.unread ?? 0), 0)
  const nav: NavItem[] = [
    { to: '/parent', label: '메시지 작성', icon: <PenIcon />, end: true },
    { to: '/parent/chats', label: '대화 목록', icon: <ChatIcon />, badge: unread },
    { to: '/parent/support', label: '담당자 채팅', icon: <ChatIcon /> },
    { to: '/parent/calendar', label: '캘린더', icon: <CalendarIcon /> },
    { to: '/parent/notices', label: '공지사항', icon: <NoticeIcon /> },
  ]
  return (
    <AppShell title="학부모" nav={<BottomNav items={nav} label="학부모 메뉴" />}>
      <Routes>
        <Route index element={<ParentCompose />} />
        <Route path="pick" element={<ScenarioPicker />} />
        <Route path="chats" element={<ParentConversationTab />} />
        <Route path="support" element={<ParentComplaintChat />} />
        <Route path="calendar" element={<ParentCalendar />} />
        <Route path="notices/*" element={<ParentNotices />} />
        <Route path="*" element={<Navigate to="/parent" replace />} />
      </Routes>
    </AppShell>
  )
}
