import { useState, useEffect, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { apiFetch } from '../lib/api'
import { useAuth } from '../lib/AuthContext'

// Pull FastAPI's {"detail": "..."} out of the Error apiFetch throws
// (its message looks like `API 402: {"detail":"You're out of credits."}`).
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

const POLL_INTERVAL_MS = 1500

// A tool_event message stores a small JSON blob; render it as a subtle chip.
function ToolChip({ content }) {
  let data = {}
  try {
    data = JSON.parse(content)
  } catch {
    /* ignore */
  }
  let label
  if (data.tool === 'web_search') label = `Searched: ${data.query}`
  else if (data.tool === 'create_pdf_report') label = `Creating report: ${data.title}`
  else label = data.tool || 'Working…'

  const icon = data.tool === 'create_pdf_report' ? '📄' : '🔍'
  return (
    <div className="flex justify-start">
      <span className="inline-flex max-w-full items-center gap-1.5 rounded-full border border-gray-200 bg-white px-3 py-1 text-xs text-gray-600">
        <span className="shrink-0">{icon}</span>
        <span className="truncate">{label}</span>
      </span>
    </div>
  )
}

function MessageItem({ msg }) {
  if (msg.role === 'tool_event') return <ToolChip content={msg.content} />

  if (msg.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] whitespace-pre-wrap rounded-2xl bg-gray-900 px-4 py-2.5 text-sm text-white">
          {msg.content}
        </div>
      </div>
    )
  }

  // assistant
  return (
    <div className="flex justify-start">
      <div className="max-w-[80%] rounded-2xl bg-white px-4 py-3 shadow-sm ring-1 ring-gray-100">
        <div className="markdown">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
        </div>
        {msg.artifact_url && (
          <a
            href={msg.artifact_url}
            target="_blank"
            rel="noreferrer"
            className="mt-3 inline-flex items-center gap-2 rounded-lg border border-gray-900 px-3 py-1.5 text-xs font-medium text-gray-900 transition hover:bg-gray-900 hover:text-white"
          >
            ⬇ Download PDF report
          </a>
        )}
      </div>
    </div>
  )
}

export default function Chat() {
  const { profile, refreshProfile } = useAuth()

  const [threads, setThreads] = useState([])
  const [currentThreadId, setCurrentThreadId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [keysPresent, setKeysPresent] = useState(null) // null = loading
  const [error, setError] = useState(null)

  const pollRef = useRef(null)
  const threadIdRef = useRef(null) // avoids stale closures in the poll timer
  const scrollRef = useRef(null)

  const credits = profile?.credits ?? 0
  const outOfCredits = credits <= 0

  // --- data loading ---------------------------------------------------------
  const fetchMessages = useCallback(async (tid) => {
    if (!tid) return
    try {
      const rows = await apiFetch(`/api/threads/${tid}/messages`)
      // Only apply if the user hasn't switched away mid-request.
      if (threadIdRef.current === tid) setMessages(rows)
    } catch {
      /* transient during a run — keep the last good render */
    }
  }, [])

  const loadThreads = useCallback(async () => {
    try {
      const rows = await apiFetch('/api/threads')
      setThreads(rows)
    } catch (err) {
      setError(errorDetail(err, 'Could not load your chats.'))
    }
  }, [])

  useEffect(() => {
    loadThreads()
    apiFetch('/api/keys')
      .then((rows) => setKeysPresent(rows.length > 0))
      .catch(() => setKeysPresent(false))
  }, [loadThreads])

  // Stop polling on unmount.
  useEffect(() => () => stopPolling(), [])

  // Auto-scroll to the newest message.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
  }, [messages])

  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  function startPolling(tid) {
    stopPolling()
    pollRef.current = setInterval(() => fetchMessages(tid), POLL_INTERVAL_MS)
  }

  function selectThread(id) {
    if (sending) return
    setError(null)
    threadIdRef.current = id
    setCurrentThreadId(id)
    setMessages([])
    fetchMessages(id)
  }

  function newChat() {
    if (sending) return
    setError(null)
    threadIdRef.current = null
    setCurrentThreadId(null)
    setMessages([])
  }

  // --- sending --------------------------------------------------------------
  async function handleSend(e) {
    e.preventDefault()
    const text = input.trim()
    if (!text || sending || outOfCredits || !keysPresent) return

    setError(null)
    setSending(true)

    let tid = currentThreadId
    try {
      // Create the thread up front so we can poll it live from the first message.
      if (!tid) {
        const thread = await apiFetch('/api/threads', {
          method: 'POST',
          body: JSON.stringify({ title: text }),
        })
        tid = thread.id
        threadIdRef.current = tid
        setCurrentThreadId(tid)
        setThreads((prev) => [thread, ...prev])
      }

      // Optimistic user bubble; polling replaces it with the persisted rows.
      setMessages((prev) => [
        ...prev,
        { id: `temp-${Date.now()}`, role: 'user', content: text },
      ])
      setInput('')
      startPolling(tid)

      await apiFetch('/api/chat', {
        method: 'POST',
        body: JSON.stringify({ thread_id: tid, message: text }),
      })
    } catch (err) {
      setError(errorDetail(err, 'The agent run failed. Please try again.'))
    } finally {
      stopPolling()
      await fetchMessages(tid)
      await refreshProfile() // credits changed (spent, or refunded on failure)
      await loadThreads() // reflect any new title
      setSending(false)
    }
  }

  const inputDisabled = sending || outOfCredits || keysPresent === false

  return (
    <div className="flex h-[calc(100vh-3.55rem)] overflow-hidden">
      {/* Sidebar */}
      <aside className="flex w-64 flex-none flex-col border-r border-gray-200 bg-white">
        <div className="p-3">
          <button
            onClick={newChat}
            disabled={sending}
            className="w-full rounded-lg bg-gray-900 px-3 py-2 text-sm font-medium text-white transition hover:bg-gray-700 disabled:opacity-60"
          >
            + New chat
          </button>
        </div>
        <nav className="flex-1 overflow-y-auto px-2 pb-3">
          {threads.length === 0 ? (
            <p className="px-2 py-4 text-xs text-gray-400">No chats yet.</p>
          ) : (
            threads.map((t) => (
              <button
                key={t.id}
                onClick={() => selectThread(t.id)}
                disabled={sending}
                className={`mb-1 block w-full truncate rounded-lg px-3 py-2 text-left text-sm transition disabled:opacity-60 ${
                  t.id === currentThreadId
                    ? 'bg-gray-100 font-medium text-gray-900'
                    : 'text-gray-600 hover:bg-gray-50'
                }`}
                title={t.title}
              >
                {t.title}
              </button>
            ))
          )}
        </nav>
      </aside>

      {/* Main */}
      <main className="flex flex-1 flex-col bg-gray-50">
        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl space-y-4 px-6 py-6">
            {messages.length === 0 && !sending && (
              <div className="mt-20 text-center text-gray-400">
                <p className="text-lg font-medium text-gray-500">
                  What do you want to research?
                </p>
                <p className="mt-1 text-sm">
                  Ask a question and MicroManus will search the web, cite its
                  sources, and can produce a downloadable PDF report.
                </p>
              </div>
            )}

            {messages.map((m) => (
              <MessageItem key={m.id} msg={m} />
            ))}

            {sending && (
              <div className="flex justify-start">
                <span className="inline-flex items-center gap-2 rounded-full border border-gray-200 bg-white px-3 py-1 text-xs text-gray-500">
                  <span className="h-2 w-2 animate-pulse rounded-full bg-gray-400" />
                  MicroManus is working…
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Composer */}
        <div className="border-t border-gray-200 bg-white px-6 py-4">
          <div className="mx-auto max-w-3xl">
            {keysPresent === false && (
              <p className="mb-2 text-sm text-gray-500">
                Add your API key in{' '}
                <Link to="/settings" className="font-medium text-gray-900 underline">
                  Settings
                </Link>{' '}
                to start chatting.
              </p>
            )}
            {outOfCredits && keysPresent !== false && (
              <p className="mb-2 text-sm text-gray-500">
                You're out of credits. Chatting is disabled.
              </p>
            )}
            {error && (
              <p className="mb-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </p>
            )}

            <form onSubmit={handleSend} className="flex items-end gap-2">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleSend(e)
                  }
                }}
                rows={1}
                placeholder={
                  inputDisabled ? 'Chatting is disabled' : 'Ask anything…'
                }
                disabled={inputDisabled}
                className="max-h-40 flex-1 resize-none rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:border-gray-900 focus:outline-none disabled:bg-gray-100 disabled:opacity-60"
              />
              <button
                type="submit"
                disabled={inputDisabled || !input.trim()}
                className="rounded-xl bg-gray-900 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-gray-700 disabled:opacity-60"
              >
                {sending ? 'Running…' : 'Send'}
              </button>
            </form>
          </div>
        </div>
      </main>
    </div>
  )
}
