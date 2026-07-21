import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { useAuth } from './lib/AuthContext'
import RequireAuth from './components/RequireAuth'
import NavBar from './components/NavBar'
import Login from './pages/Login'
import Paywall from './pages/Paywall'
import Chat from './pages/Chat'
import Settings from './pages/Settings'
import Stats from './pages/Stats'

function homeForProfile(profile) {
  return profile?.unlocked ? '/chat' : '/paywall'
}

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

function AppLayout() {
  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <NavBar />
      <Outlet />
    </div>
  )
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
        <Route element={<AppLayout />}>
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
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
