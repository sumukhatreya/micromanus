import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../lib/AuthContext'
import { apiFetch } from '../lib/api'

// Pull FastAPI's {"detail": "..."} message out of the Error apiFetch throws
// (its message looks like `API 400: {"detail":"Invalid coupon"}`).
function errorDetail(err, fallback) {
  const match = /API \d+: (.*)$/s.exec(err?.message ?? '')
  if (match) {
    try {
      return JSON.parse(match[1]).detail ?? fallback
    } catch {
      /* not JSON — fall through */
    }
  }
  return fallback
}

export default function Paywall() {
  const { profile, refreshProfile, signOut } = useAuth()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const [coupon, setCoupon] = useState('')
  const [couponBusy, setCouponBusy] = useState(false)
  const [payBusy, setPayBusy] = useState(false)
  const [shouldPoll, setShouldPoll] = useState(false)
  const [polling, setPolling] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  const status = searchParams.get('status')

  // If the profile becomes unlocked (coupon here, or the Stripe webhook landing),
  // there's nothing left to do on the paywall — go to chat.
  useEffect(() => {
    if (profile?.unlocked) navigate('/chat', { replace: true })
  }, [profile?.unlocked, navigate])

  // Handle the URL status param from Stripe redirect (one-time).
  useEffect(() => {
    if (status === 'success') {
      setShouldPoll(true)
      setPolling(true)
      setNotice('Payment successful — adding your 5 credits…')
    } else if (status === 'cancel') {
      setNotice('Checkout canceled. You can try again anytime.')
    }
    if (status) setSearchParams({}, { replace: true })
  }, [status, setSearchParams])

  // Poll for unlock separately so setSearchParams cleanup can't cancel it.
  useEffect(() => {
    if (!shouldPoll) return
    let cancelled = false
    const poll = async () => {
      for (let i = 0; i < 20; i++) {
        if (cancelled) return
        await new Promise((r) => setTimeout(r, 1500))
        try {
          await refreshProfile()
        } catch {
          /* transient — keep polling */
        }
      }
      if (!cancelled) {
        setNotice(null)
        setError(
          "Payment received, but crediting is taking longer than expected. Refresh in a moment — if it doesn't unlock, contact support.",
        )
        setPolling(false)
        setShouldPoll(false)
      }
    }
    poll()
    return () => { cancelled = true }
  }, [shouldPoll, refreshProfile])

  async function handleRedeem(e) {
    e.preventDefault()
    setError(null)
    setNotice(null)
    setCouponBusy(true)
    try {
      await apiFetch('/api/paywall/redeem-coupon', {
        method: 'POST',
        body: JSON.stringify({ code: coupon.trim() }),
      })
      setNotice('Coupon redeemed — 5 credits added!')
      await refreshProfile() // flips `unlocked`; the effect above routes to /chat
    } catch (err) {
      setError(errorDetail(err, 'Could not redeem coupon. Please try again.'))
    } finally {
      setCouponBusy(false)
    }
  }

  async function handlePay() {
    setError(null)
    setNotice(null)
    setPayBusy(true)
    try {
      const { url } = await apiFetch('/api/paywall/create-checkout-session', {
        method: 'POST',
      })
      window.location.href = url // redirect to Stripe Checkout
    } catch (err) {
      setError(errorDetail(err, 'Could not start checkout. Please try again.'))
      setPayBusy(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <header className="border-b border-gray-200 bg-white">
        <nav className="mx-auto flex max-w-4xl items-center px-6 py-4 text-sm">
          <span className="font-semibold">MicroManus</span>
          <button
            onClick={signOut}
            disabled={polling}
            className="ml-auto text-gray-500 hover:text-gray-900 disabled:opacity-60"
          >
            Sign out
          </button>
        </nav>
      </header>

      <main className="mx-auto max-w-2xl px-6 py-16">
        <h1 className="text-2xl font-semibold">Unlock MicroManus</h1>
        <p className="mt-2 text-gray-500">
          Get <span className="font-medium text-gray-900">5 credits</span> to start
          researching. Redeem a coupon or pay $5 (test mode).
        </p>

        {notice && (
          <div className="mt-6 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
            {notice}
          </div>
        )}
        {error && (
          <div className="mt-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="mt-8 grid gap-6 sm:grid-cols-2">
          {/* Coupon card */}
          <form
            onSubmit={handleRedeem}
            className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm"
          >
            <h2 className="font-medium">Have a coupon?</h2>
            <p className="mt-1 text-sm text-gray-500">
              Enter your code to unlock instantly.
            </p>
            <input
              type="text"
              value={coupon}
              onChange={(e) => setCoupon(e.target.value)}
              placeholder="Coupon code"
              disabled={polling}
              className="mt-4 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-gray-900 focus:outline-none disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={polling || couponBusy || !coupon.trim()}
              className="mt-3 w-full rounded-lg bg-gray-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-gray-700 disabled:opacity-60"
            >
              {couponBusy ? 'Redeeming…' : 'Redeem coupon'}
            </button>
          </form>

          {/* Stripe card */}
          <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
            <h2 className="font-medium">Pay with card</h2>
            <p className="mt-1 text-sm text-gray-500">
              $5.00 one-time · 5 credits. Test mode — use card{' '}
              <code className="rounded bg-gray-100 px-1">4242 4242 4242 4242</code>.
            </p>
            <button
              onClick={handlePay}
              disabled={polling || payBusy}
              className="mt-4 w-full rounded-lg border border-gray-900 px-4 py-2.5 text-sm font-medium text-gray-900 transition hover:bg-gray-900 hover:text-white disabled:opacity-60"
            >
              {payBusy ? 'Redirecting…' : 'Pay $5'}
            </button>
          </div>
        </div>
      </main>
    </div>
  )
}
