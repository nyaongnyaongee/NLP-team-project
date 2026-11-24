import { useCallback } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { listComplaintChats } from '../../api/complaints'
import type { ComplaintChatSummary } from '../../api/types'
import AppShell from '../../components/AppShell'
import BottomNav, { type NavItem } from '../../components/BottomNav'
import { CalendarIcon, ChatIcon, ComplaintIcon, NoticeIcon, StudentIcon, TodoIcon } from '../../components/icons'
import TeacherNotices from '../notices/TeacherNotices'
import CalendarTab from '../tasks/CalendarTab'
import TodosTab from '../tasks/TodosTab'
import { useConversations } from '../chat/useConversations'
import { useResource } from '../chat/useResource'
import { useOpenTodoCount } from '../tasks/useOpenTodoCount'
import { useSync } from '../../realtime/useSync'
import ConversationsTab from './ConversationsTab'
import StudentsTab from './StudentsTab'
import TeacherComplaints from '../complaints/TeacherComplaints'
import DemoCardsPage from '../demo/DemoCardsPage'

const EMPTY_CHATS: ComplaintChatSummary[] = []

// 교사 화면의 틀: 위에 계정 표시, 가운데에 탭 내용, 아래에 탭 메뉴 (명세 8장 주소 구조: /teacher/...)
export default function TeacherHome() {
  const { conversations } = useConversations()
  const unread = conversations.reduce((n, c) => n + (c.unread ?? 0), 0)
  const loadComplaintChats = useCallback(() => listComplaintChats('teacher'), [])
  const { data: complaintChats, loaded: chatsLoaded, error: chatsError, refresh: refreshChats } = useResource(loadComplaintChats, EMPTY_CHATS)
  useSync('teacher-complaint-chats', refreshChats, (event) => event.type === 'complaints')
  const complaintUnread = complaintChats.reduce((n, chat) => n + (chat.unread_count ?? 0), 0)
  const todos = useOpenTodoCount()
  const nav: NavItem[] = [
    { to: '/teacher', label: '대화 목록', icon: <ChatIcon />, end: true, badge: unread },
    { to: '/teacher/todos', label: '투두리스트', icon: <TodoIcon />, badge: todos ?? undefined },
    { to: '/teacher/calendar', label: '캘린더', icon: <CalendarIcon /> },
    { to: '/teacher/students', label: '학생', icon: <StudentIcon /> },
    { to: '/teacher/notices', label: '공지사항', icon: <NoticeIcon /> },
    { to: '/teacher/complaints', label: '민원 이관', icon: <ComplaintIcon />, badge: complaintUnread },
  ]
  return (
    <AppShell title="교사" nav={<BottomNav items={nav} label="교사 메뉴" />}>
      <Routes>
        <Route index element={<ConversationsTab />} />
        <Route path="todos" element={<TodosTab />} />
        <Route path="calendar" element={<CalendarTab />} />
        <Route path="students/*" element={<StudentsTab />} />
        <Route path="cards" element={<DemoCardsPage />} />
        <Route path="notices/*" element={<TeacherNotices />} />
        <Route path="complaints/*" element={
          <TeacherComplaints chats={complaintChats} chatsLoaded={chatsLoaded} chatsError={chatsError} refreshChats={refreshChats} />
        } />
        <Route path="*" element={<Navigate to="/teacher" replace />} />
      </Routes>
    </AppShell>
  )
}
