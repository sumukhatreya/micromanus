# Minimus

A deep-research AI agent web app with usage-based billing. Bring your own LLM
key, ask a research question, and watch an agent loop search the web, read
sources, and synthesize a cited answer — optionally exported as a downloadable
PDF report. Every run is metered per token and priced per the model you chose.

- **Frontend:** React (JavaScript) + Vite + Tailwind, hosted on Vercel
- **Backend:** FastAPI (Python 3.13, `uv`), hosted on Railway
- **Auth / DB / Storage:** Supabase (GitHub OAuth, Postgres, private file bucket)
- **Payments:** Stripe (test mode)
- **Agent:** OpenAI Python SDK (one client, swapped `base_url` per provider) + Tavily web search

---

## Features

- **GitHub login** via Supabase OAuth.
- **$5 paywall** with two unlock paths: a coupon (`USE_MINIMUS`) or Stripe
  Checkout (test card `4242 4242 4242 4242`). Both grant 5 credits.
- **Bring your own key (BYOK):** add an OpenAI, Anthropic, or Moonshot (Kimi)
  key; keys are Fernet-encrypted at rest and never returned in full.
- **Agentic research loop:** the model calls `web_search` (Tavily) iteratively —
  refining queries — then answers with source citations. Tool activity is shown
  live in the chat.
- **PDF artifacts:** ask for a report and the agent renders Markdown → PDF
  (pure-Python `xhtml2pdf`), uploads it to Supabase Storage, and returns a
  signed download link.
- **Threaded chats** with persistent history and follow-up context.
- **Usage & cost tracking:** per-thread breakdown of input / output / cached
  tokens, priced per model, on a dedicated stats page.
- **1 credit per user message**; chat is blocked at 0 credits.

## Architecture

```
[React SPA (Vite) on Vercel]
   │  Supabase JS client → GitHub OAuth, obtains a JWT
   │  fetch() with Authorization: Bearer <supabase JWT>
   ▼
[FastAPI on Railway]
   ├─ verifies the Supabase JWT on every route (except /health, Stripe webhook)
   ├─ Supabase Postgres (service_role key) — all tables, scoped by JWT user_id
   ├─ Stripe (test mode) — checkout session + webhook
   ├─ Agent loop — OpenAI SDK pointed at the user's provider base_url
   ├─ Tavily — web_search tool
   └─ xhtml2pdf — PDF artifact → Supabase Storage → signed URL
```

`PLAN.md` is the authoritative spec for the full design, schema, and rationale.

## Repository layout

```
/frontend            React + Vite (JavaScript) + Tailwind SPA
  src/pages/         Login, Paywall, Chat, Settings, Stats
  vercel.json        SPA rewrite + Vite build config
/backend             FastAPI service (uv-managed)
  app/routes/        me, paywall, models, keys, chat, stats
  app/agent.py       the research agent loop
  app/tools.py       web_search + create_pdf_report
  app/models_config.py  providers, model IDs, and pricing (verified 2026-07-21)
  railway.json       Railway deploy config
  nixpacks.toml      Railway build (uv sync + uvicorn)
/supabase/schema.sql Postgres tables + profile trigger (paste into Supabase)
/PLAN.md             authoritative spec
```

---

## Local development

### Prerequisites

- Python 3.13 and [`uv`](https://docs.astral.sh/uv/)
- Node.js 18+ and npm
- Accounts/keys: Supabase project, Stripe (test mode), Tavily, and at least one
  LLM provider key for testing. See `PLAN.md` §A1 for the full account list.

### 1. Supabase schema

In the Supabase SQL editor, paste and run `supabase/schema.sql` (creates all
tables plus the `profiles` trigger). Then create a **private** Storage bucket
named `artifacts`.

### 2. Backend

```bash
cd backend
cp .env.example .env          # then fill in the values (see below)
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

Health check: <http://localhost:8000/health> → `{"status":"ok"}`.

Generate a Fernet `ENCRYPTION_KEY` once with:

```bash
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

For local Stripe webhooks, in a separate terminal:

```bash
stripe listen --forward-to localhost:8000/api/stripe/webhook
```

Copy the CLI's signing secret into `STRIPE_WEBHOOK_SECRET`. (Note: the local CLI
secret differs from the deployed dashboard secret.)

### 3. Frontend

```bash
cd frontend
cp .env.example .env          # fill in Supabase + API base URL
npm install
npm run dev                   # http://localhost:5173
```

## Environment variables

**`backend/.env`** (see `backend/.env.example`)

| Variable | Purpose |
|---|---|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-side DB access (bypasses RLS) |
| `SUPABASE_JWT_SECRET` | Validates incoming user JWTs |
| `ENCRYPTION_KEY` | Fernet key encrypting stored API keys |
| `STRIPE_SECRET_KEY` | Stripe test-mode secret key |
| `STRIPE_WEBHOOK_SECRET` | Verifies Stripe webhook signatures |
| `TAVILY_API_KEY` | Web search for the agent |
| `FRONTEND_URL` | Allowed CORS origin + Stripe redirect target |

**`frontend/.env`** (see `frontend/.env.example`)

| Variable | Purpose |
|---|---|
| `VITE_SUPABASE_URL` | Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Supabase anon (public) key |
| `VITE_API_BASE_URL` | Backend base URL (no trailing slash) |

Secrets live only in `.env` files, which are git-ignored. The `.env.example`
files are the tracked source of truth for which variables are required.

## Deployment

The backend deploys to **Railway** (root dir `/backend`, config in
`railway.json` + `nixpacks.toml`) and the frontend to **Vercel** (root dir
`/frontend`, config in `vercel.json`). See `PLAN.md` §B9 for the full,
step-by-step deploy and post-deploy wiring checklist.

## Testing

Run the acceptance checklist in `PLAN.md` §A5 against a fresh account in an
incognito window — it covers login, the paywall (both unlock paths), BYOK, the
agent loop, PDF export, credit decrement, and the stats page.

## Security notes

- Every backend route validates the Supabase JWT and scopes DB queries by the
  authenticated `user_id`; a `user_id` is never trusted from the request body.
- The Stripe webhook is unauthenticated by design — its signature verification
  is its auth.
- LLM keys are Fernet-encrypted at rest and returned only masked (`sk-...xyz`).
- Stripe runs in **test mode only**; no real money moves.
