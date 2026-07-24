import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../lib/AuthContext'

export default function NavBar({ disabled }) {
  const { session, profile, signOut } = useAuth()
  const { pathname } = useLocation()

  const linkClass = (path) => {
    if (disabled) return 'pointer-events-none opacity-50'
    return pathname === path ? 'font-medium text-gray-900' : 'hover:text-gray-900'
  }

  return (
    <header className="border-b border-gray-200 bg-white">
      <nav className="mx-auto flex max-w-4xl items-center gap-4 px-6 py-4 text-sm">
        <span className="font-semibold">Minimus</span>
        {profile?.unlocked && (
          <div className="flex gap-3 text-gray-500">
            <Link className={linkClass('/chat')} to="/chat" tabIndex={disabled ? -1 : undefined} aria-disabled={disabled || undefined}>Chat</Link>
            <Link className={linkClass('/settings')} to="/settings" tabIndex={disabled ? -1 : undefined} aria-disabled={disabled || undefined}>Settings</Link>
            <Link className={linkClass('/stats')} to="/stats" tabIndex={disabled ? -1 : undefined} aria-disabled={disabled || undefined}>Stats</Link>
          </div>
        )}
        {session && (
          <div className="ml-auto flex items-center gap-4">
            {profile && (
              <span className="text-gray-500">{profile.credits} credits</span>
            )}
            <button
              onClick={signOut}
              className="text-gray-500 hover:text-gray-900"
            >
              Sign out
            </button>
          </div>
        )}
      </nav>
    </header>
  )
}
