import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell from '../../components/AppShell'
import BottomNav, { type NavItem } from '../../components/BottomNav'
import { CalendarIcon, ChatIcon, NoticeIcon, TodoIcon } from '../../components/icons'
import TeacherNotices from '../notices/TeacherNotices'
import CalendarTab from '../tasks/CalendarTab'
import TodosTab from '../tasks/TodosTab'
import ConversationsTab from './ConversationsTab'

const NAV: NavItem[] = [
  { to: '/teacher', label: '대화 목록', icon: <ChatIcon />, end: true },
  { to: '/teacher/todos', label: '할 일', icon: <TodoIcon /> },
  { to: '/teacher/calendar', label: '캘린더', icon: <CalendarIcon /> },
  { to: '/teacher/notices', label: '공지사항', icon: <NoticeIcon /> },
]

// 교사 화면의 틀: 위에 계정 표시, 가운데에 탭 내용, 아래에 탭 메뉴 (명세 8장 주소 구조: /teacher/...)
export default function TeacherHome() {
  return (
    <AppShell title="교사" nav={<BottomNav items={NAV} label="교사 메뉴" />}>
      <Routes>
        <Route index element={<ConversationsTab />} />
        <Route path="todos" element={<TodosTab />} />
        <Route path="calendar" element={<CalendarTab />} />
        <Route path="notices/*" element={<TeacherNotices />} />
        <Route path="*" element={<Navigate to="/teacher" replace />} />
      </Routes>
    </AppShell>
  )
}
