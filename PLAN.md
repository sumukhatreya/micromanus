# Minimus — Execution Plan

Deep-research AI agent web app with usage-based billing. Built with FastAPI (Python) + React (JavaScript, not TS). This document is the single source of truth: Part A is for the human (accounts, workflow, testing), Part B is the technical spec to be executed by Claude Code.

---

# PART A — HUMAN SETUP & WORKFLOW

## A1. External services and accounts to create (do this BEFORE coding)

Create all of these up front so you never block an agent session waiting on an account approval.

| # | Service | Purpose | Account type / plan | What you'll need from it |
|---|---------|---------|--------------------|--------------------------|
| 1 | **GitHub** | Code hosting + the OAuth provider for user login | Your existing account | Repo; a **GitHub OAuth App** (created later, Supabase gives you the callback URL) |
| 2 | **Supabase** | Auth (GitHub social login), Postgres DB, file storage for generated PDFs | Free tier, new project | Project URL, `anon` key, `service_role` key, DB connection string |
| 3 | **Stripe** | $5 paywall payment | Free developer account, **test mode only** — never activate live mode | Test-mode publishable key, secret key, webhook signing secret |
| 4 | **Vercel** | Host the React frontend | Free (Hobby) | Connect via GitHub |
| 5 | **Railway** (primary) or **Render** (fallback) | Host the FastAPI backend | Railway: Hobby plan ~$5 for the month (worth it — no cold starts). Render free tier works but sleeps after 15 min idle → 30–50 s cold start, bad for reviewers; if using Render free, set up a cron ping (cron-job.org, free, every 10 min) | Deployed backend URL |
| 6 | **Tavily** | Web search API for the agent's search tool | Free tier (~1,000 calls, no card needed). Alternative: Brave Search API free tier | `TAVILY_API_KEY` |
| 7 | **OpenAI and/or Moonshot (Kimi)** | YOUR test key for developing/testing the chat (users bring their own key; you never pre-load one in the app) | ~$5 of credit on one provider is enough. Moonshot (platform.moonshot.ai) is the cheapest option | An API key kept in your local `.env` for testing only |

Decisions locked in:
- **Social login = GitHub only.** The assignment says "github or google is ok" — one provider suffices. GitHub is fastest to set up via Supabase and the reviewers are engineers who all have GitHub.
- **Payments = Stripe test mode.** Reviewer pays with test card `4242 4242 4242 4242`, any future expiry, any CVC. No real money ever moves. Do not create live-mode keys.
- **Search key (Tavily) is app-level** and lives in the backend env. This is fine — the "do not pre-load key" rule applies to LLM keys only.

## A2. Total expected cost

- Railway hobby month: ~$5 (cancel after) — or $0 with Render + cron ping
- LLM test credit: ~$5
- Domain: $0 (use `something.vercel.app`; assignment only requires a web URL)
- Everything else: $0
- **Total: $5–10**

## A3. Claude Code — first-time setup (meta-instructions for YOU)

1. **Install:** `npm install -g @anthropic-ai/claude-code`, then run `claude` in a terminal and log in when prompted (Claude subscription or API billing).
2. **Create the repo:**
   ```bash
   # on github.com: create empty repo "minimus" (private is fine until submission)
   git clone https://github.com/<you>/minimus.git
   cd minimus
   ```
3. **Seed the repo with context:** copy THIS file into the repo as `PLAN.md`. Then create `CLAUDE.md` at the repo root containing:
   ```
   Read PLAN.md before doing anything. It is the authoritative spec.
   Stack: FastAPI backend in /backend, React (Vite, JavaScript — NOT TypeScript) frontend in /frontend.
   Never hardcode secrets; use .env files and keep .env in .gitignore. Maintain .env.example files.
   After completing a phase, tell me exactly how to run and test it manually.
   Do not invent LLM model IDs or prices — verify them via web search or ask me.
   ```
   Claude Code automatically reads `CLAUDE.md` at the start of every session.
4. **Working rhythm — one phase per session:**
   - Start `claude` in the repo root.
   - Press **Shift+Tab** to switch to **Plan Mode** first. Paste the phase prompt (given at the end of each phase in Part B). Claude will propose a plan without touching files — read it, correct it, then approve to let it implement.
   - When it finishes, it will have edited files directly. Review with `git diff` (or `git diff --stat` first for the shape, then file by file).
   - **Test manually** using the phase's test checklist below. Don't move on until the phase works.
   - Commit: `git add -A && git commit -m "Phase N: <name>"` then `git push`.
   - Run `/clear` in Claude Code (or start a fresh session) before the next phase — a small, clean context makes agents noticeably more reliable.
5. **Branching:** for a solo 1-day project, work directly on `main` with one commit per verified phase. Use a branch (`git checkout -b experiment`) only if you want to try something risky; merge or delete after. Don't burn time on PR ceremony against yourself.
6. **Reviewing agent code — what to actually look for** (you don't need to read every line):
   - Secrets: grep for `sk-`, `whsec_`, hardcoded keys. Must be zero outside `.env`.
   - Money/credits paths: read `payments.py` and the credit-deduction logic fully — this is where bugs embarrass you.
   - Auth: every backend route except `/health` and the Stripe webhook must verify the Supabase JWT.
   - Everything else: skim for structure, trust the tests you run by hand.
7. **When the agent gets stuck or loops:** interrupt (Esc), describe the observed error (paste the traceback/console output verbatim), and ask it to diagnose before fixing. Pasting real error output works far better than describing the bug from memory.

## A4. Suggested schedule (1 focused day + testing morning)

- **Hour 0–1:** All accounts (A1), repo setup (A3).
- **Hours 1–3:** Phases 1–3 (scaffold, auth, paywall).
- **Hours 3–6:** Phases 4–5 (BYOK + agent loop — the core).
- **Hours 6–8:** Phases 6–7 (PDF, stats page).
- **Hours 8–9:** Phase 8 (deploy).
- **Next morning:** Full test pass (A5), friend test, fix, submit.

## A5. Final acceptance test (run yourself, then have a friend run it cold)

The assignment disqualifies broken submissions, so this list IS the deliverable:

1. Open the Vercel URL in an incognito window → land on signup → GitHub login works.
2. Immediately after signup you hit a **paywall**. You cannot reach chat by URL-hacking (`/chat` redirects back to paywall).
3. Coupon `USE_MINIMUS` unlocks and shows **5 credits**. (Test with account #1.)
4. Stripe path: test card `4242 4242 4242 4242` → payment succeeds → 5 credits. (Test with account #2 — each account should exercise one path.)
5. Wrong coupon shows an error; paying/redeeming twice doesn't stack weirdly.
6. Add an API key: pick provider + model, paste key → save succeeds; a bad key shows a clear error on first chat, not a crash.
7. Chat: ask *"Create a report explaining the recent forest fires in California, what causes them and what can be done"* → visibly see the agent loop (searching → reading → searching again) → get a cited answer → PDF artifact downloadable.
8. Follow-up question in the same thread uses prior context ("summarize that report in 3 bullets").
9. New chat button starts a fresh thread; old thread still listed and re-openable with history intact.
10. Credits decrement per message; at 0 credits, chat is blocked with a clear message.
11. Stats page: per-thread cost, split into input / output / cached tokens, priced per the model used.
12. Log out, log back in — everything persists.
13. Friend test: send the URL + their own API key path to a friend with ZERO instructions. If they get confused anywhere, fix that UX. "Everything else has to be self-explanatory" is an explicit grading criterion.

---

# PART B — TECHNICAL SPEC (feed to Claude Code phase by phase)

## B0. Architecture overview

```
[React SPA (Vite, JS) on Vercel]
   │  Supabase JS client → GitHub OAuth login, gets JWT
   │  fetch() with Authorization: Bearer <supabase JWT>
   ▼
[FastAPI on Railway]
   ├─ verifies Supabase JWT on every route
   ├─ Supabase Postgres (via supabase-py, service_role key) — all tables
   ├─ Stripe (test mode) — checkout session + webhook
   ├─ Agent loop — OpenAI python SDK pointed at user's provider base_url
   ├─ Tavily — web_search tool
   └─ WeasyPrint/ReportLab — PDF artifact → Supabase Storage → signed URL
```

Repo layout (monorepo):
```
/frontend        # Vite + React (JavaScript), Tailwind
/backend         # FastAPI, uv or pip + requirements.txt
/PLAN.md         # this file
/CLAUDE.md       # agent instructions
```

## B1. Database schema (Supabase Postgres)

Run as SQL in the Supabase SQL editor (agent generates the migration file; human pastes it in — simpler than wiring migrations for a 1-day project).

```sql
-- profiles: created via trigger on auth.users insert
create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  credits int not null default 0,
  unlocked boolean not null default false,        -- passed paywall
  unlock_method text,                             -- 'coupon' | 'stripe'
  created_at timestamptz default now()
);

create table api_keys (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references profiles(id) on delete cascade,
  provider text not null,          -- 'openai' | 'anthropic' | 'kimi'
  model text not null,             -- model id chosen at key-add time
  encrypted_key text not null,     -- Fernet-encrypted, key in backend env
  created_at timestamptz default now()
);

create table threads (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references profiles(id) on delete cascade,
  title text not null default 'New chat',
  created_at timestamptz default now()
);

create table messages (
  id uuid primary key default gen_random_uuid(),
  thread_id uuid references threads(id) on delete cascade,
  role text not null,              -- 'user' | 'assistant' | 'tool_event'
  content text not null,           -- tool_event rows store a short JSON blob for UI display
  artifact_url text,               -- signed URL if a PDF was produced
  created_at timestamptz default now()
);

create table usage_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references profiles(id) on delete cascade,
  thread_id uuid references threads(id) on delete cascade,
  model text not null,
  input_tokens int not null default 0,
  output_tokens int not null default 0,
  cached_tokens int not null default 0,
  cost_usd numeric(10,6) not null default 0,
  created_at timestamptz default now()
);

create table coupon_redemptions (
  user_id uuid primary key references profiles(id) on delete cascade,
  code text not null,
  redeemed_at timestamptz default now()
);
```

Notes for the agent:
- Add the standard Supabase trigger that inserts a `profiles` row when a user signs up.
- The backend talks to the DB with the `service_role` key, so RLS can stay off for speed — BUT then every backend route must scope queries by the authenticated `user_id` from the JWT. Never trust a user_id from the request body.
- Supabase Storage: create a private bucket `artifacts`; PDFs uploaded there; return 7-day signed URLs.

## B2. Auth flow

- Frontend uses `@supabase/supabase-js` → `signInWithOAuth({ provider: 'github' })`.
- Human setup step: in Supabase dashboard → Auth → Providers → GitHub, follow instructions (create a GitHub OAuth App at github.com/settings/developers with the callback URL Supabase displays). Also add the Vercel domain AND `http://localhost:5173` to Supabase Auth → URL Configuration → Redirect URLs.
- Backend: dependency `get_current_user` that validates the `Authorization: Bearer` JWT. Validate against the Supabase JWT secret (Project Settings → API → JWT Secret) using `python-jose`, extract `sub` as user_id. Reject with 401 otherwise.
- Route gating in React: if not logged in → login page; if logged in but `profile.unlocked == false` → paywall page; else → app. Enforce the same on the backend: chat/stats routes return 402 if `unlocked` is false or `credits <= 0` (frontend surfaces this properly).

## B3. Paywall (coupon + Stripe test mode)

Endpoints:
- `POST /api/paywall/redeem-coupon {code}` → if code === `USE_MINIMUS` (exact, compare server-side) and user not already unlocked → set `unlocked=true, unlock_method='coupon', credits=5`, insert redemption row. Errors: wrong code (400 "Invalid coupon"), already unlocked (409).
- `POST /api/paywall/create-checkout-session` → Stripe Checkout Session, test mode: `mode='payment'`, line item $5.00 USD "Minimus — 5 credits", `client_reference_id=user_id`, success/cancel URLs back to the frontend. Return the session URL; frontend redirects.
- `POST /api/stripe/webhook` → verify signature with `STRIPE_WEBHOOK_SECRET`, handle `checkout.session.completed`: set `unlocked=true, unlock_method='stripe', credits += 5`. Idempotent (check unlock state / store processed session id). This route is UNauthenticated (Stripe calls it) — signature verification is its auth.
- Frontend paywall page: two cards — "Have a coupon?" input + "Pay $5" button. After success, show "5 credits added" and route to chat.
- Human setup: Stripe dashboard (test mode) → Developers → Webhooks → add endpoint `https://<backend>/api/stripe/webhook`, event `checkout.session.completed`, copy signing secret to backend env. For local testing use `stripe listen --forward-to localhost:8000/api/stripe/webhook` (Stripe CLI).

Credit consumption rule (assignment leaves it open — we define it): **1 credit per user message sent to the agent** (one full agent run, regardless of tool-call count). Deduct at run start; show remaining credits in the navbar.

## B4. BYOK — models & providers

`POST /api/keys` {provider, model, api_key} — encrypt api_key with Fernet (`cryptography` lib, `ENCRYPTION_KEY` in backend env) before storing. `GET /api/keys` returns provider+model+masked key (`sk-...xyz`), never the full key. Latest saved key = active key. `DELETE /api/keys/{id}` supported.

One LLM client for all providers via the OpenAI python SDK with swapped `base_url`:

| provider | base_url | notes |
|----------|----------|-------|
| openai | `https://api.openai.com/v1` | native |
| anthropic | `https://api.anthropic.com/v1/` | OpenAI-compatibility endpoint |
| kimi | `https://api.moonshot.ai/v1` | natively OpenAI-compatible |

Model list lives in ONE config file `backend/app/models_config.py`: for each provider, 3–4 current popular model ids + pricing per 1M tokens for input / output / cached-input. **AGENT: do not trust your memory for model IDs or prices — verify each provider's current model names and per-token pricing via web search at build time, and note in a code comment the date you checked.** The frontend fetches this config from `GET /api/models` to populate the picker.

Caching behavior (what "caching in place" means here): rely on provider-side prompt caching — OpenAI caches long repeated prompt prefixes automatically; Kimi has automatic context caching; Anthropic's compat layer has limited caching support, so cached_tokens may legitimately be 0 there. What we MUST do: read the `usage` object off every response — `prompt_tokens`, `completion_tokens`, and `prompt_tokens_details.cached_tokens` when present — and log all three to `usage_logs` with computed `cost_usd = (uncached_input × in_price) + (cached × cached_price) + (output × out_price)`. Structure the conversation so caching can work: static system prompt first, then history, so the prefix repeats across turns.

## B5. The agent loop (core of the project)

`POST /api/chat` {thread_id | null, message} → if thread_id null, create thread (title = first ~40 chars of message). Persist the user message. Deduct 1 credit (402 if none). Then run:

```
messages = [system_prompt] + full thread history (from DB)
for iteration in range(MAX_ITER = 10):
    resp = client.chat.completions.create(model=..., messages=..., tools=TOOLS)
    log usage from resp.usage → usage_logs row
    if resp has tool_calls:
        for each tool_call:
            persist a 'tool_event' message (e.g. {"tool":"web_search","query":"..."})
            result = execute tool
            append assistant tool_call msg + tool result msg to messages
        continue loop
    else:
        persist final assistant message; break
```

Tools (OpenAI function-calling format):
1. `web_search(query: str)` → Tavily API (`tavily-python`), return top 5 results as `[{title, url, snippet/content}]` JSON string. Instruct the model in the system prompt to cite source URLs in answers.
2. `create_pdf_report(title: str, markdown_content: str)` → render markdown to PDF (WeasyPrint via `markdown` lib → HTML → PDF; fallback ReportLab if WeasyPrint's system deps annoy the host — check Railway supports WeasyPrint's libpango deps, else use `fpdf2`+`markdown-it` or ReportLab). Upload to Supabase Storage `artifacts/`, create signed URL, set `artifact_url` on the final assistant message, return the URL to the model so it can mention it.

System prompt (agent: write ~15 lines): you are Minimus, a deep-research agent; decompose questions; search multiple times with refined queries before answering; synthesize with citations; call create_pdf_report when the user asks for a report/document; be concise otherwise.

API response to frontend: the final assistant message + artifact_url + the ordered list of tool_events (so the UI can show "🔍 Searched: california wildfires 2026" steps). Streaming is NOT required — acceptable UX: optimistic user bubble, then a live-ish activity area. Implementation: simplest robust option is the frontend polling `GET /api/threads/{id}/messages` every 1.5 s while a run is active (tool_event rows appear as the loop persists them), stopping when the final assistant message lands. (If the agent proposes SSE and it works, fine — but don't sink time into it.)

Other endpoints: `GET /api/threads` (sidebar list), `GET /api/threads/{id}/messages`, `POST /api/threads` (new chat).

## B6. Stats / cost page

`GET /api/stats` → per-thread aggregation from `usage_logs` joined to `threads`: thread title, model(s) used, total input/output/cached tokens, cost per category, total cost; plus grand totals. Frontend: a table (one row per thread, expandable or with columns for the token split) + summary cards (total spend, total tokens, chats count).

## B7. Frontend structure (React, JavaScript, Vite, Tailwind)

Pages: `/login`, `/paywall`, `/chat` (sidebar: thread list + New Chat; main: messages incl. tool-activity steps rendered as subtle inline chips, artifact download button on messages with artifact_url; input box; credits badge in navbar), `/settings` (API key add/list/delete, provider+model picker), `/stats`.
- `react-router-dom`, Supabase client for auth/session, a tiny `api.js` wrapper adding the JWT header, `react-markdown` for assistant messages.
- Keep design clean and minimal (reference: Perplexity's layout). Dark mode not required. Self-explanatory > pretty: empty states with one-line instructions ("Add your API key in Settings to start chatting" with a link).

## B8. Environment variables

`backend/.env` (mirror in `.env.example` with blanks):
```
SUPABASE_URL=            SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_JWT_SECRET=     ENCRYPTION_KEY=          # Fernet key, generate once
STRIPE_SECRET_KEY=       STRIPE_WEBHOOK_SECRET=
TAVILY_API_KEY=          FRONTEND_URL=            # for CORS + Stripe redirects
```
`frontend/.env`:
```
VITE_SUPABASE_URL=       VITE_SUPABASE_ANON_KEY=
VITE_API_BASE_URL=
```
CORS: allow only `FRONTEND_URL` and localhost:5173.

## B9. Deployment

- **Backend → Railway:** connect GitHub repo, root dir `/backend`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Set all env vars. Confirm WeasyPrint deps (or use the pure-python PDF fallback). Note the public URL.
- **Frontend → Vercel:** import repo, root dir `/frontend`, framework Vite. Set env vars (API base = Railway URL). Add SPA rewrite (all routes → index.html) via `vercel.json`.
- Post-deploy wiring: add Vercel URL to Supabase redirect URLs; update GitHub OAuth App callback if needed; point Stripe webhook at the Railway URL; set `FRONTEND_URL`.
- Smoke-test the full A5 checklist against production, not just localhost.

## B10. Phase prompts (paste these into Claude Code, one session each, Plan Mode first)

- **Phase 1 — Scaffold:** "Read PLAN.md. Execute section B0's repo layout: scaffold /backend (FastAPI, health route, CORS per B8, settings loader for env vars) and /frontend (Vite + React JS + Tailwind + react-router with empty pages per B7). Give me run instructions for both dev servers."
- **Phase 2 — Auth:** "Read PLAN.md B1–B2. Generate the SQL migration for me to paste into Supabase (all tables + profile trigger). Implement Supabase GitHub login on the frontend, the get_current_user JWT dependency on the backend, and route gating (login → paywall → app). Walk me through the Supabase/GitHub OAuth dashboard setup steps precisely."
- **Phase 3 — Paywall:** "Read PLAN.md B3. Implement coupon redemption, Stripe test-mode checkout, the webhook, credits, and the paywall page. Include stripe CLI instructions for local webhook testing."
- **Phase 4 — BYOK:** "Read PLAN.md B4. Implement api_keys endpoints with Fernet encryption, models_config.py (verify current model IDs and prices via web search; comment the date), /api/models, and the Settings page."
- **Phase 5 — Agent loop:** "Read PLAN.md B5. Implement the agent loop, both tools, thread/message endpoints, credit deduction, usage logging, and the chat UI with tool-activity display and polling."
- **Phase 6 — PDF artifact:** "Read PLAN.md B5 tool 2. Implement create_pdf_report end-to-end including Supabase Storage upload and the download button in chat." (Merged into Phase 5 if it went smoothly.)
- **Phase 7 — Stats:** "Read PLAN.md B6. Implement /api/stats and the stats page."
- **Phase 8 — Deploy:** "Read PLAN.md B9. Prepare deployment configs (vercel.json, Railway settings, .env.example completeness) and give me a step-by-step deploy checklist."

## B11. Known pitfalls (agent + human, read before Phase 5)

1. Agents inventing model IDs/prices — that's why verification is mandated in B4.
2. Anthropic via the OpenAI-compat endpoint: some params unsupported; keep requests to plain messages + tools; if tool-calling misbehaves there, it's acceptable to note in the UI that provider X has best support — but try first.
3. Tool-call message ordering: the assistant message containing `tool_calls` must be appended to history BEFORE the `role:"tool"` result messages, each carrying the right `tool_call_id`. Most agent-loop bugs are here.
4. Stripe webhook 400s: usually a wrong signing secret (CLI secret ≠ dashboard secret) — they differ between local and deployed.
5. Supabase JWT validation failing: use the JWT Secret (legacy HS256) from Project Settings → API; if the project uses the newer asymmetric keys, validate via JWKS instead — ask the agent to detect and handle whichever the project has.
6. CORS errors after deploy: FRONTEND_URL not updated to the Vercel domain.
7. Vercel SPA 404s on refresh: missing rewrite in vercel.json.
8. WeasyPrint native deps failing on the host: switch to the pure-python fallback rather than debugging system packages.
