import { useState, useEffect, useMemo } from 'react'
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

export default function Settings() {
  const [providers, setProviders] = useState([])
  const [keys, setKeys] = useState([])
  const [loading, setLoading] = useState(true)

  const [provider, setProvider] = useState('')
  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')

  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  // Models available for the currently selected provider.
  const models = useMemo(
    () => providers.find((p) => p.provider === provider)?.models ?? [],
    [providers, provider],
  )

  async function loadKeys() {
    const rows = await apiFetch('/api/keys')
    setKeys(rows)
  }

  // Initial load: model catalog + existing keys.
  useEffect(() => {
    let active = true
    ;(async () => {
      try {
        const [cfg, rows] = await Promise.all([
          apiFetch('/api/models'),
          apiFetch('/api/keys'),
        ])
        if (!active) return
        setProviders(cfg)
        setKeys(rows)
        // Default the picker to the first provider/model.
        if (cfg.length) {
          setProvider(cfg[0].provider)
          setModel(cfg[0].models[0]?.id ?? '')
        }
      } catch (err) {
        if (active) setError(errorDetail(err, 'Could not load settings. Please refresh.'))
      } finally {
        if (active) setLoading(false)
      }
    })()
    return () => {
      active = false
    }
  }, [])

  // When the provider changes, reset the model to that provider's first option.
  function handleProviderChange(next) {
    setProvider(next)
    const first = providers.find((p) => p.provider === next)?.models[0]?.id ?? ''
    setModel(first)
  }

  async function handleSave(e) {
    e.preventDefault()
    setError(null)
    setNotice(null)
    setSaving(true)
    try {
      await apiFetch('/api/keys', {
        method: 'POST',
        body: JSON.stringify({ provider, model, api_key: apiKey.trim() }),
      })
      setApiKey('')
      setNotice('API key saved. Your latest key is the active one.')
      await loadKeys()
    } catch (err) {
      setError(errorDetail(err, 'Could not save the key. Please try again.'))
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(id) {
    setError(null)
    setNotice(null)
    try {
      await apiFetch(`/api/keys/${id}`, { method: 'DELETE' })
      await loadKeys()
    } catch (err) {
      setError(errorDetail(err, 'Could not delete the key. Please try again.'))
    }
  }

  const providerLabel = (key) =>
    providers.find((p) => p.provider === key)?.label ?? key

  return (
      <main className="mx-auto max-w-2xl px-6 py-12">
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="mt-2 text-gray-500">
          Add your own LLM API key (BYOK). The latest key you save is used for
          chat. Keys are encrypted at rest and never shown in full again.
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

        {/* Add-key form */}
        <form
          onSubmit={handleSave}
          className="mt-8 space-y-4 rounded-xl border border-gray-200 bg-white p-6 shadow-sm"
        >
          <h2 className="font-medium">Add an API key</h2>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="text-gray-700">Provider</span>
              <select
                value={provider}
                onChange={(e) => handleProviderChange(e.target.value)}
                disabled={loading || !providers.length}
                className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-gray-900 focus:outline-none disabled:opacity-60"
              >
                {providers.map((p) => (
                  <option key={p.provider} value={p.provider}>
                    {p.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="block text-sm">
              <span className="text-gray-700">Model</span>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                disabled={loading || !models.length}
                className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-gray-900 focus:outline-none disabled:opacity-60"
              >
                {models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label} — ${m.price.input}/${m.price.output} per 1M in/out
                  </option>
                ))}
              </select>
            </label>
          </div>

          <label className="block text-sm">
            <span className="text-gray-700">API key</span>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Paste your provider API key"
              autoComplete="off"
              disabled={loading}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-gray-900 focus:outline-none disabled:opacity-60"
            />
          </label>

          <button
            type="submit"
            disabled={loading || saving || !provider || !model || !apiKey.trim()}
            className="w-full rounded-lg bg-gray-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-gray-700 disabled:opacity-60 sm:w-auto"
          >
            {saving ? 'Saving…' : 'Save key'}
          </button>
        </form>

        {/* Saved keys */}
        <section className="mt-8">
          <h2 className="font-medium">Your keys</h2>
          {loading ? (
            <p className="mt-2 text-sm text-gray-500">Loading…</p>
          ) : keys.length === 0 ? (
            <p className="mt-2 text-sm text-gray-500">
              No keys yet. Add one above to start chatting.
            </p>
          ) : (
            <ul className="mt-3 divide-y divide-gray-200 overflow-hidden rounded-xl border border-gray-200 bg-white">
              {keys.map((k, i) => (
                <li
                  key={k.id}
                  className="flex items-center gap-4 px-4 py-3 text-sm"
                >
                  <div className="min-w-0">
                    <div className="font-medium">
                      {providerLabel(k.provider)} · {k.model}
                      {i === 0 && (
                        <span className="ml-2 rounded bg-green-100 px-1.5 py-0.5 text-xs font-normal text-green-800">
                          active
                        </span>
                      )}
                    </div>
                    <div className="text-gray-500">
                      <code>{k.masked_key}</code>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(k.id)}
                    className="ml-auto text-gray-400 hover:text-red-600"
                  >
                    Delete
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
  )
}
