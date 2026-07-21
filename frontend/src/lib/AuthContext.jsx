import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { supabase } from './supabase'
import { apiFetch } from './api'

// Central auth state: the Supabase session plus the backend profile (credits,
// unlock status) used for route gating (PLAN.md §B2). `loading` stays true until
// we've resolved both, so guards don't redirect on a flash of "no session".
const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null)
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)

  const loadProfile = useCallback(async (activeSession) => {
    if (!activeSession) {
      setProfile(null)
      return
    }
    try {
      const me = await apiFetch('/api/me')
      setProfile(me)
    } catch (err) {
      // Keep the user gated (treated as locked) rather than crashing the app.
      setProfile(null)
    }
  }, [])

  useEffect(() => {
    let active = true

    supabase.auth.getSession().then(async ({ data: { session: s } }) => {
      if (!active) return
      setSession(s)
      await loadProfile(s)
      if (active) setLoading(false)
    })

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(async (_event, s) => {
      if (!active) return
      setSession(s)
      await loadProfile(s)
      if (active) setLoading(false)
    })

    return () => {
      active = false
      subscription.unsubscribe()
    }
  }, [loadProfile])

  const signInWithGitHub = useCallback(
    () =>
      supabase.auth.signInWithOAuth({
        provider: 'github',
        options: { redirectTo: window.location.origin },
      }),
    [],
  )

  const signOut = useCallback(() => supabase.auth.signOut(), [])

  const refreshProfile = useCallback(async () => {
    const { data: { session: s } } = await supabase.auth.getSession()
    await loadProfile(s)
  }, [loadProfile])


  const value = {
    session,
    profile,
    loading,
    signInWithGitHub,
    signOut,
    refreshProfile,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
