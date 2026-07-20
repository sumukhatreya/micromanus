import { Navigate } from 'react-router-dom'
import { useAuth } from '../lib/AuthContext'

// Route guard enforcing login → paywall → app (PLAN.md §B2).
//   - not signed in           → /login
//   - signed in but locked    → /paywall  (unless requireUnlocked=false)
// `requireUnlocked={false}` is used by the /paywall route itself, which needs a
// session but not an unlock.
export default function RequireAuth({ children, requireUnlocked = true }) {
  const { session, profile, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 text-gray-500">
        Loading…
      </div>
    )
  }

  if (!session) {
    return <Navigate to="/login" replace />
  }

  if (requireUnlocked && !profile?.unlocked) {
    return <Navigate to="/paywall" replace />
  }

  return children
}
