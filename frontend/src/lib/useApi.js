import { useCallback, useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext.jsx'

// Fetch-on-mount hook with loading/error/retry and automatic session drop on 401.
// fetcher: (token, studentId, signal) => Promise<data>
export function useApi(fetcher, deps = []) {
  const { token, studentId, handleAuthError } = useAuth()
  const [state, setState] = useState({ data: null, loading: true, error: null })
  const [nonce, setNonce] = useState(0)

  const retry = useCallback(() => setNonce((n) => n + 1), [])

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    setState((s) => ({ ...s, loading: true, error: null }))
    Promise.resolve(fetcher(token, studentId, controller.signal))
      .then((data) => {
        if (active) setState({ data, loading: false, error: null })
      })
      .catch((err) => {
        if (err?.name === 'AbortError') return
        handleAuthError(err)
        if (active) setState({ data: null, loading: false, error: err })
      })
    return () => {
      active = false
      controller.abort()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, studentId, nonce, ...deps])

  return { ...state, retry }
}
