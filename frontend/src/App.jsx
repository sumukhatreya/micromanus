import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './lib/AuthContext'
import RequireAuth from './components/RequireAuth'
import Login from './pages/Login'
import Paywall from './pages/Paywall'
import Chat from './pages/Chat'
import Settings from './pages/Settings'
import Stats from './pages/Stats'

// Where a signed-in user belongs: the app if unlocked, else the paywall.
function homeForProfile(profile) {
  return profile?.unlocked ? '/chat' : '/paywall'
}

// `/` and `/login`: send an already-authenticated user onward instead of
// showing the login screen again.
function EntryRedirect({ children }) {
  const { session, profile, loading } = useAuth()
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 text-gray-500">
        Loading…
      </div>
    )
  }
  if (session) return <Navigate to={homeForProfile(profile)} replace />
  return children
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={
            <EntryRedirect>
              <Navigate to="/login" replace />
            </EntryRedirect>
          }
        />
        <Route
          path="/login"
          element={
            <EntryRedirect>
              <Login />
            </EntryRedirect>
          }
        />
        <Route
          path="/paywall"
          element={
            <RequireAuth requireUnlocked={false}>
              <Paywall />
            </RequireAuth>
          }
        />
        <Route
          path="/chat"
          element={
            <RequireAuth>
              <Chat />
            </RequireAuth>
          }
        />
        <Route
          path="/settings"
          element={
            <RequireAuth>
              <Settings />
            </RequireAuth>
          }
        />
        <Route
          path="/stats"
          element={
            <RequireAuth>
              <Stats />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
