import { Navigate, Route, Routes } from 'react-router-dom'
import RequireAuth from './components/RequireAuth'
import { UiProvider } from './lib/ui'
import ChatPage from './pages/ChatPage'
import KnowledgePage from './pages/KnowledgePage'
import LoginPage from './pages/LoginPage'
import ProfilePage from './pages/ProfilePage'
import RegisterPage from './pages/RegisterPage'

export default function App() {
  return (
    <UiProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route
          path="/chat"
          element={
            <RequireAuth>
              <ChatPage />
            </RequireAuth>
          }
        />
        <Route
          path="/knowledge"
          element={
            <RequireAuth>
              <KnowledgePage />
            </RequireAuth>
          }
        />
        <Route
          path="/profile"
          element={
            <RequireAuth>
              <ProfilePage />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Routes>
    </UiProvider>
  )
}