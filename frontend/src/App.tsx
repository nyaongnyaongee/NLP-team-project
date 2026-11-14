import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth/AuthContext'
import RequireRole from './auth/RequireRole'
import { HOME_PATH } from './auth/roles'
import LoginPage from './features/login/LoginPage'
import ParentHome from './features/parent/ParentHome'
import TeacherHome from './features/teacher/TeacherHome'
import TeamHome from './features/team/TeamHome'
import { RealtimeProvider } from './realtime/RealtimeContext'

// 알 수 없는 주소와 "/" 는 로그인 상태에 따라 보낸다.
function Fallback() {
  const { session } = useAuth()
  return <Navigate to={session ? HOME_PATH[session.role] : '/login'} replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        {/* 로그인한 동안 서버 알림 연결 하나를 열고, 대화·공지 화면이 나눠 쓴다 */}
        <RealtimeProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/parent/*"
              element={
                <RequireRole role="parent">
                  <ParentHome />
                </RequireRole>
              }
            />
            <Route
              path="/teacher/*"
              element={
                <RequireRole role="teacher">
                  <TeacherHome />
                </RequireRole>
              }
            />
            <Route
              path="/team/*"
              element={
                <RequireRole role="complaint_team">
                  <TeamHome />
                </RequireRole>
              }
            />
            <Route path="*" element={<Fallback />} />
          </Routes>
        </RealtimeProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
