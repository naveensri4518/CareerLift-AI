import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, clearSession, loadSession, saveSession } from '../api/client.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [session, setSession] = useState(() => loadSession())

  // Keep localStorage in sync.
  useEffect(() => {
    if (session) saveSession(session)
  }, [session])

  const register = useCallback(async (displayName) => {
    // The SERVER generates the identity (student_id) and token. The client never chooses them.
    const res = await api.register(displayName)
    const next = { student_id: res.student_id, token: res.token, display_name: displayName || null }
    setSession(next)
    saveSession(next)
    return next
  }, [])

  const logout = useCallback(() => {
    clearSession()
    setSession(null)
  }, [])

  // Any API call that 401s should drop the session so the app returns to sign-in.
  const handleAuthError = useCallback((err) => {
    if (err && err.kind === 'auth') {
      clearSession()
      setSession(null)
    }
  }, [])

  const value = useMemo(
    () => ({
      session,
      isAuthed: !!session?.token,
      studentId: session?.student_id || null,
      token: session?.token || null,
      register,
      logout,
      handleAuthError,
    }),
    [session, register, logout, handleAuthError],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
