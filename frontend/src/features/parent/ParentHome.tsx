import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell from '../../components/AppShell'
import BottomNav, { type NavItem } from '../../components/BottomNav'
import { ChatIcon, NoticeIcon } from '../../components/icons'
import ParentNotices from '../notices/ParentNotices'
import ParentConversationTab from './ParentConversationTab'

const NAV: NavItem[] = [
  { to: '/parent', label: '대화', icon: <ChatIcon />, end: true },
  { to: '/parent/notices', label: '공지사항', icon: <NoticeIcon /> },
]

// 학부모 화면의 틀: 위에 계정 표시, 가운데에 탭 내용, 아래에 탭 메뉴 (명세 8장 주소 구조: /parent/...)
export default function ParentHome() {
  return (
    <AppShell title="학부모" nav={<BottomNav items={NAV} label="학부모 메뉴" />}>
      <Routes>
        <Route index element={<ParentConversationTab />} />
        <Route path="notices/*" element={<ParentNotices />} />
        <Route path="*" element={<Navigate to="/parent" replace />} />
      </Routes>
    </AppShell>
  )
}
