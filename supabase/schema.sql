-- MicroManus — database schema (PLAN.md §B1)
-- Paste this into the Supabase SQL editor and run once.
--
-- Design notes:
--   * All app tables live in `public`.
--   * RLS stays OFF: the backend talks to Postgres with the service_role key and
--     scopes every query by the JWT-derived user_id. Never trust a user_id from a
--     request body.
--   * `profiles` rows are created automatically by the trigger at the bottom when a
--     user signs up via Supabase Auth (auth.users insert).

-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------

create table if not exists profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  credits int not null default 0,
  unlocked boolean not null default false,        -- passed paywall
  unlock_method text,                             -- 'coupon' | 'stripe'
  created_at timestamptz default now()
);

create table if not exists api_keys (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references profiles(id) on delete cascade,
  provider text not null,          -- 'openai' | 'anthropic' | 'kimi'
  model text not null,             -- model id chosen at key-add time
  encrypted_key text not null,     -- Fernet-encrypted, key in backend env
  created_at timestamptz default now()
);

create table if not exists threads (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references profiles(id) on delete cascade,
  title text not null default 'New chat',
  cancelled boolean not null default false,
  created_at timestamptz default now()
);

create table if not exists messages (
  id uuid primary key default gen_random_uuid(),
  thread_id uuid references threads(id) on delete cascade,
  role text not null,              -- 'user' | 'assistant' | 'tool_event'
  content text not null,           -- tool_event rows store a short JSON blob for UI display
  artifact_url text,               -- signed URL if a PDF was produced
  artifact_title text,             -- clean display name for the PDF download button
  created_at timestamptz default now()
);

create table if not exists usage_logs (
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

create table if not exists coupon_redemptions (
  user_id uuid primary key references profiles(id) on delete cascade,
  code text not null,
  redeemed_at timestamptz default now()
);

-- stripe_events: webhook idempotency ledger (PLAN.md §B3). Stripe retries event
-- delivery, so each processed event id is recorded here; a re-delivered event
-- hits the primary-key conflict and is skipped instead of adding credits twice.
create table if not exists stripe_events (
  id text primary key,             -- stripe event id (evt_...)
  processed_at timestamptz default now()
);

-- ---------------------------------------------------------------------------
-- Storage bucket for PDF artifacts (PLAN.md §B1)
-- Private bucket: objects are only reachable through the 7-day signed URLs the
-- backend mints in app/storage.py. Equivalent to creating it by hand in
-- Storage → New bucket (public = off).
--
-- Convenience only, and deliberately non-fatal: an existing bucket is left
-- untouched, and if this role can't write storage.buckets we swallow it rather
-- than aborting the rest of this script. The backend creates the bucket on
-- first upload anyway if it's still missing.
-- ---------------------------------------------------------------------------

do $$
begin
  insert into storage.buckets (id, name, public)
  values ('artifacts', 'artifacts', false)
  on conflict (id) do nothing;
exception
  when insufficient_privilege or undefined_table then
    raise notice 'Skipped creating the artifacts bucket; create it in Storage (private) if it does not exist.';
end
$$;

-- ---------------------------------------------------------------------------
-- Row Level Security
-- Enable RLS with NO policies on every table. This denies the public `anon` and
-- `authenticated` roles all access via the auto-generated REST API, closing the
-- direct-table-access hole from shipping a public anon key. The backend uses the
-- service_role key, which bypasses RLS entirely, so nothing else changes.
-- ---------------------------------------------------------------------------

alter table profiles           enable row level security;
alter table api_keys           enable row level security;
alter table threads            enable row level security;
alter table messages           enable row level security;
alter table usage_logs         enable row level security;
alter table coupon_redemptions enable row level security;
alter table stripe_events      enable row level security;

-- ---------------------------------------------------------------------------
-- Profile auto-provisioning trigger
-- Inserts a profiles row whenever a new auth user is created.
-- ---------------------------------------------------------------------------

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = ''
as $$
begin
  insert into public.profiles (id) values (new.id);
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();
