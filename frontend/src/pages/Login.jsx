import { useState } from 'react'
import { useAuth } from '../lib/AuthContext'

export default function Login() {
  const { signInWithGitHub } = useAuth()
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function handleLogin() {
    setBusy(true)
    setError(null)
    const { error: err } = await signInWithGitHub()
    if (err) {
      setError(err.message)
      setBusy(false)
    }
    // On success the browser redirects to GitHub, so no need to reset `busy`.
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm rounded-xl border border-gray-200 bg-white p-8 shadow-sm">
        <h1 className="text-center text-2xl font-semibold text-gray-900">Minimus</h1>
        <p className="mt-2 text-center text-sm text-gray-500">
          Your deep-research AI agent. Sign in to get started.
        </p>

        <button
          onClick={handleLogin}
          disabled={busy}
          className="mt-8 flex w-full items-center justify-center gap-2 rounded-lg bg-gray-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-gray-700 disabled:opacity-60"
        >
          <svg viewBox="0 0 16 16" width="18" height="18" fill="currentColor" aria-hidden="true">
            <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0016 8c0-4.42-3.58-8-8-8z" />
          </svg>
          {busy ? 'Redirecting…' : 'Sign in with GitHub'}
        </button>

        {error && <p className="mt-4 text-center text-sm text-red-600">{error}</p>}
      </div>
    </div>
  )
}
