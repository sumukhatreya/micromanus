import { Link } from 'react-router-dom'

// Shared placeholder shell for the Phase 1 scaffold. Real page content
// (auth, paywall, chat, settings, stats) lands in later phases.
export default function Page({ title, children }) {
  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <header className="border-b border-gray-200 bg-white">
        <nav className="mx-auto flex max-w-4xl items-center gap-4 px-6 py-4 text-sm">
          <span className="font-semibold">MicroManus</span>
          <div className="flex gap-3 text-gray-500">
            <Link className="hover:text-gray-900" to="/login">Login</Link>
            <Link className="hover:text-gray-900" to="/paywall">Paywall</Link>
            <Link className="hover:text-gray-900" to="/chat">Chat</Link>
            <Link className="hover:text-gray-900" to="/settings">Settings</Link>
            <Link className="hover:text-gray-900" to="/stats">Stats</Link>
          </div>
        </nav>
      </header>
      <main className="mx-auto max-w-4xl px-6 py-16">
        <h1 className="text-2xl font-semibold">{title}</h1>
        <p className="mt-2 text-gray-500">{children}</p>
      </main>
    </div>
  )
}
