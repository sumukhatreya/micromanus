import { createClient } from '@supabase/supabase-js'

// Frontend uses the public anon key. GitHub OAuth + session persistence are
// handled by supabase-js (PLAN.md §B2).
const url = import.meta.env.VITE_SUPABASE_URL
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

if (!url || !anonKey) {
  // Surfaced early so a missing frontend/.env is obvious, not a blank screen.
  console.error(
    'Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY — copy frontend/.env.example to frontend/.env and fill them in.',
  )
}

export const supabase = createClient(url, anonKey)
