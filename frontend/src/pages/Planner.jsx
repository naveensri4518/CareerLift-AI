import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, CalendarClock, Compass, Lightbulb, Mic } from 'lucide-react'
import { motion } from 'framer-motion'
import { Card, EmptyState, ErrorState, LoadingBlock, SectionHeading, Spinner } from '../components/ui.jsx'
import { api } from '../api/client.js'
import { useApi } from '../lib/useApi.js'
import { useAuth } from '../context/AuthContext.jsx'
import { topicLabel } from '../lib/content.js'

export default function Planner() {
  const { token } = useAuth()
  const navigate = useNavigate()
  const { data, loading, error, retry } = useApi((t, id) => api.next(t, id))
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState(null)

  const startRecommended = async () => {
    if (!data?.topic) return
    setStarting(true)
    setStartError(null)
    try {
      // Begin an interview on the recommended topic, then hand off to Practice via router state.
      const iv = await api.startInterview(token, { topic: data.topic })
      navigate('/app/practice', { state: { prestarted: iv } })
    } catch (err) {
      // Fall back WITHOUT losing the recommendation: go to Practice with the recommended topic
      // preselected so the user still lands on the right exercise and can start it manually.
      setStartError(err.message)
      navigate('/app/practice', { state: { topic: data.topic } })
    } finally {
      setStarting(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-white">Learning Planner</h1>
        <p className="mt-1 text-sm text-slate-400">
          A personalised next step, chosen from your real practice so far.
        </p>
      </div>

      {loading ? (
        <Card className="p-6"><LoadingBlock rows={4} /></Card>
      ) : error ? (
        <Card className="p-6"><ErrorState message={error.message} onRetry={retry} /></Card>
      ) : !data ? (
        <Card className="p-6">
          <EmptyState title="No recommendation yet" hint="Practise a question and we’ll suggest your next step." />
        </Card>
      ) : (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <Card glow className="p-6">
            <SectionHeading icon={Compass} title="Recommended next exercise" />
            <div className="mt-5 rounded-2xl border border-brand-purple/20 bg-brand-soft p-5">
              <p className="text-xs font-medium uppercase tracking-wide text-brand-violet">Topic</p>
              <h2 className="mt-1 text-xl font-extrabold text-white">{topicLabel(data.topic)}</h2>
              <div className="mt-3 flex items-start gap-2 text-sm text-slate-300">
                <Lightbulb size={16} className="mt-0.5 shrink-0 text-brand-violet" />
                <p>
                  <span className="font-semibold text-slate-200">Why this: </span>
                  {data.reason}
                </p>
              </div>
              {data.question ? (
                <p className="mt-4 rounded-xl border border-white/10 bg-ink-900/60 p-3 text-sm leading-relaxed text-slate-300">
                  {data.question}
                </p>
              ) : null}
            </div>

            {startError ? <div className="mt-4"><ErrorState message={startError} /></div> : null}

            <div className="mt-5 flex flex-wrap gap-3">
              <button className="btn-primary !py-3" onClick={startRecommended} disabled={starting}>
                {starting ? <Spinner label="Starting…" /> : (
                  <>
                    <Mic size={15} /> Start this exercise
                  </>
                )}
              </button>
              <button className="btn-ghost !py-3" onClick={() => navigate('/app/practice')}>
                Choose a different topic <ArrowRight size={15} />
              </button>
            </div>
          </Card>

          <div className="mt-5 grid gap-4 sm:grid-cols-3">
            {[
              { n: '1', t: 'Practise', d: 'Answer the recommended question in your own words.' },
              { n: '2', t: 'Review', d: 'See your separate technical and communication results with evidence.' },
              { n: '3', t: 'Improve', d: 'Fix any detected misconception, then come back for the next step.' },
            ].map((s) => (
              <Card key={s.n} className="p-4">
                <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-soft text-sm font-bold text-brand-violet">
                  {s.n}
                </span>
                <p className="mt-2 text-sm font-semibold text-white">{s.t}</p>
                <p className="mt-1 text-xs text-slate-500">{s.d}</p>
              </Card>
            ))}
          </div>
        </motion.div>
      )}
    </div>
  )
}
