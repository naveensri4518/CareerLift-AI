import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, Copy, Check, KeyRound, ShieldCheck, TriangleAlert } from 'lucide-react'
import { Logo } from '../components/Logo.jsx'
import { Card, ErrorState, Spinner } from '../components/ui.jsx'
import { useAuth } from '../context/AuthContext.jsx'

export default function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [displayName, setDisplayName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [created, setCreated] = useState(null) // { student_id, token }
  const [copied, setCopied] = useState(false)
  const [savedAck, setSavedAck] = useState(false)

  const onCreate = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const res = await register(displayName.trim())
      setCreated(res)
    } catch (err) {
      setError(err.message || 'Could not create your account.')
    } finally {
      setLoading(false)
    }
  }

  const copyToken = async () => {
    try {
      await navigator.clipboard.writeText(created.token)
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    } catch {
      /* clipboard may be blocked; the token is visible to copy manually */
    }
  }

  return (
    <div className="min-h-screen bg-ink-950 dotted-grid">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-80 bg-[radial-gradient(60%_60%_at_50%_0%,rgba(99,102,241,0.18),transparent)]" />
      <header className="relative mx-auto flex max-w-5xl items-center justify-between px-5 py-5">
        <Link to="/">
          <Logo />
        </Link>
        <Link to="/" className="text-sm text-slate-400 hover:text-slate-200">
          Back to home
        </Link>
      </header>

      <main className="relative mx-auto grid min-h-[70vh] max-w-md place-items-center px-5">
        {!created ? (
          <Card glow className="w-full p-7">
            <span className="grid h-11 w-11 place-items-center rounded-xl bg-brand-soft text-brand-violet">
              <KeyRound size={20} />
            </span>
            <h1 className="mt-4 text-xl font-bold text-white">Create your practice account</h1>
            <p className="mt-2 text-sm leading-relaxed text-slate-400">
              Accounts are anonymous. We generate a private access token for you — there is no email or
              password. You will save the token to come back to your progress.
            </p>

            <form onSubmit={onCreate} className="mt-6 space-y-4">
              <div>
                <label htmlFor="displayName" className="mb-1.5 block text-xs font-medium text-slate-400">
                  Display name <span className="text-slate-600">(optional, just for you)</span>
                </label>
                <input
                  id="displayName"
                  className="input"
                  placeholder="e.g. Priya"
                  value={displayName}
                  maxLength={128}
                  onChange={(e) => setDisplayName(e.target.value)}
                />
              </div>

              {error ? <ErrorState message={error} /> : null}

              <button type="submit" className="btn-primary w-full !py-3" disabled={loading}>
                {loading ? <Spinner label="Creating…" /> : (
                  <>
                    Create account <ArrowRight size={16} />
                  </>
                )}
              </button>
            </form>

            <div className="mt-5 flex items-start gap-2 rounded-xl border border-white/10 bg-white/[0.03] p-3 text-xs text-slate-400">
              <ShieldCheck size={15} className="mt-0.5 shrink-0 text-brand-violet" />
              Your identity is assigned by the service. This is a local practice prototype, not a verified
              sign-in.
            </div>
          </Card>
        ) : (
          <Card glow className="w-full p-7">
            <span className="grid h-11 w-11 place-items-center rounded-xl bg-good/15 text-good">
              <Check size={20} />
            </span>
            <h1 className="mt-4 text-xl font-bold text-white">Save your access token</h1>
            <p className="mt-2 text-sm leading-relaxed text-slate-400">
              This token is your key to your progress. It is shown{' '}
              <span className="font-semibold text-slate-200">only once</span> and cannot be recovered.
              Copy and keep it somewhere safe.
            </p>

            <div className="mt-5">
              <label className="mb-1.5 block text-xs font-medium text-slate-400">Your access token</label>
              <div className="flex items-stretch gap-2">
                <code className="flex-1 overflow-x-auto rounded-xl border border-white/10 bg-ink-900 px-3 py-2.5 text-xs text-brand-violet">
                  {created.token}
                </code>
                <button type="button" className="btn-ghost shrink-0" onClick={copyToken}>
                  {copied ? <Check size={15} /> : <Copy size={15} />}
                  {copied ? 'Copied' : 'Copy'}
                </button>
              </div>
            </div>

            <div className="mt-4 flex items-start gap-2 rounded-xl border border-warn/20 bg-warn/5 p-3 text-xs text-warn">
              <TriangleAlert size={15} className="mt-0.5 shrink-0" />
              It is saved in this browser so you can keep practising now. If you clear your browser or
              switch devices, you will need this token to return.
            </div>

            <label className="mt-5 flex cursor-pointer items-center gap-2.5 text-sm text-slate-300">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-white/20 bg-ink-900 accent-brand-purple"
                checked={savedAck}
                onChange={(e) => setSavedAck(e.target.checked)}
              />
              I have saved my access token.
            </label>

            <button
              className="btn-primary mt-5 w-full !py-3"
              disabled={!savedAck}
              onClick={() => navigate('/app')}
            >
              Go to my dashboard <ArrowRight size={16} />
            </button>
          </Card>
        )}
      </main>
    </div>
  )
}
