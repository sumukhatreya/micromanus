import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../lib/AuthContext'

export default function NavBar() {
  const { session, profile, signOut } = useAuth()
  const { pathname } = useLocation()

  const linkClass = (path) =>
    pathname === path ? 'font-medium text-gray-900' : 'hover:text-gray-900'

  return (
    <header className="border-b border-gray-200 bg-white">
      <nav className="mx-auto flex max-w-4xl items-center gap-4 px-6 py-4 text-sm">
        <span className="font-semibold">MicroManus</span>
        {profile?.unlocked && (
          <div className="flex gap-3 text-gray-500">
            <Link className={linkClass('/chat')} to="/chat">Chat</Link>
            <Link className={linkClass('/settings')} to="/settings">Settings</Link>
            <Link className={linkClass('/stats')} to="/stats">Stats</Link>
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
