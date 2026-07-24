import { useState, useEffect } from 'react'
import { apiFetch } from '../lib/api'

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

// Compact token counts: 12,345 → "12.3k". Full value stays in the title attr.
function fmtTokens(n) {
  const v = n ?? 0
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}k`
  return String(v)
}

// Costs are tiny (fractions of a cent), so show enough precision to be non-zero.
function fmtCost(n) {
  const v = n ?? 0
  if (v === 0) return '$0'
  if (v < 0.01) return `$${v.toFixed(4)}`
  return `$${v.toFixed(2)}`
}

function Card({ label, value, sub }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="text-sm text-gray-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-gray-400">{sub}</div>}
    </div>
  )
}

export default function Stats() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    ;(async () => {
      try {
        const res = await apiFetch('/api/stats')
        if (active) setData(res)
      } catch (err) {
        if (active) setError(errorDetail(err, 'Could not load stats. Please refresh.'))
      } finally {
        if (active) setLoading(false)
      }
    })()
    return () => {
      active = false
    }
  }, [])

  const totals = data?.totals
  const threads = data?.threads ?? []

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <h1 className="text-2xl font-semibold">Usage &amp; cost</h1>
      <p className="mt-2 text-gray-500">
        Token usage and estimated spend per chat, priced with the model each run
        used. Estimates come from provider list prices — your provider invoice is
        the source of truth.
      </p>

      {error && (
        <div className="mt-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading ? (
        <p className="mt-8 text-sm text-gray-500">Loading…</p>
      ) : threads.length === 0 ? (
        <p className="mt-8 text-sm text-gray-500">
          No usage yet. Head to Chat and ask the agent something — your token
          usage and cost will show up here.
        </p>
      ) : (
        <>
          {/* Summary cards */}
          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card label="Total spend" value={fmtCost(totals.cost_usd)} sub="estimated" />
            <Card
              label="Total tokens"
              value={fmtTokens(totals.total_tokens)}
              sub={`${totals.input_tokens.toLocaleString()} in · ${totals.output_tokens.toLocaleString()} out`}
            />
            <Card
              label="Cached tokens"
              value={fmtTokens(totals.cached_tokens)}
              sub="served from prompt cache"
            />
            <Card
              label="Chats"
              value={totals.thread_count}
              sub={`${totals.run_count} agent run${totals.run_count === 1 ? '' : 's'}`}
            />
          </div>

          {/* Per-thread table */}
          <div className="mt-8 overflow-x-auto rounded-xl border border-gray-200 bg-white shadow-sm">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-xs uppercase tracking-wide text-gray-500">
                  <th className="px-4 py-3 font-medium">Chat</th>
                  <th className="px-4 py-3 font-medium">Model</th>
                  <th className="px-4 py-3 text-right font-medium">Input</th>
                  <th className="px-4 py-3 text-right font-medium">Cached</th>
                  <th className="px-4 py-3 text-right font-medium">Output</th>
                  <th className="px-4 py-3 text-right font-medium">Cost</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {threads.map((t) => (
                  <tr key={t.thread_id} className="align-top">
                    <td className="max-w-[260px] px-4 py-3">
                      <div className="truncate font-medium" title={t.title}>
                        {t.title}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-600">{t.models.join(', ')}</td>
                    <td
                      className="px-4 py-3 text-right tabular-nums"
                      title={`${t.input_tokens.toLocaleString()} tokens · ${fmtCost(
                        t.cost_input,
                      )}`}
                    >
                      {fmtTokens(t.input_tokens)}
                    </td>
                    <td
                      className="px-4 py-3 text-right tabular-nums text-gray-500"
                      title={`${t.cached_tokens.toLocaleString()} tokens · ${fmtCost(
                        t.cost_cached,
                      )}`}
                    >
                      {fmtTokens(t.cached_tokens)}
                    </td>
                    <td
                      className="px-4 py-3 text-right tabular-nums"
                      title={`${t.output_tokens.toLocaleString()} tokens · ${fmtCost(
                        t.cost_output,
                      )}`}
                    >
                      {fmtTokens(t.output_tokens)}
                    </td>
                    <td className="px-4 py-3 text-right font-medium tabular-nums">
                      {fmtCost(t.cost_usd)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-gray-200 font-medium">
                  <td className="px-4 py-3" colSpan={2}>
                    Total
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {fmtTokens(totals.input_tokens)}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-gray-500">
                    {fmtTokens(totals.cached_tokens)}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {fmtTokens(totals.output_tokens)}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {fmtCost(totals.cost_usd)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </>
      )}
    </main>
  )
}
