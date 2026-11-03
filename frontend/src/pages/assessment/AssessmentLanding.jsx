import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { ArrowRight, ClipboardList, Clock, History, Info, ListChecks } from 'lucide-react'
import { motion } from 'framer-motion'
import { Card, ErrorState, LoadingBlock, SectionHeading, Spinner } from '../../components/ui.jsx'
import { api } from '../../api/client.js'
import { useApi } from '../../lib/useApi.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { categoryMeta, difficultyMeta } from '../../lib/assessment.js'

function Pill({ active, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-xl border px-3.5 py-2 text-sm transition-all ${
        active ? 'border-brand-purple/50 bg-brand-soft text-white' : 'border-white/5 bg-ink-900/60 text-slate-300 hover:border-white/10'
      }`}
    >
      {children}
    </button>
  )
}

export default function AssessmentLanding() {
  const { token } = useAuth()
  const navigate = useNavigate()
  const { data, loading, error, retry } = useApi((t) => api.assessmentCatalog(t))

  const [category, setCategory] = useState('mixed')
  const [difficulty, setDifficulty] = useState('mixed')
  const [numQuestions, setNumQuestions] = useState(10)
  const [durationMin, setDurationMin] = useState(20)
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState(null)

  const start = async () => {
    setStarting(true)
    setStartError(null)
    try {
      const res = await api.assessmentStart(token, {
        category, difficulty, num_questions: numQuestions, duration_min: durationMin,
      })
      navigate(`/app/assessment/attempt/${res.attempt_id}`)
    } catch (err) {
      setStartError(err.message)
    } finally {
      setStarting(false)
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-white">Technical Assessment</h1>
          <p className="mt-1 text-sm text-slate-400">
            Take a timed, deterministic assessment across core CS topics. Your results feed your real
            concept mastery and recommendations — no guesswork, no fabricated scores.
          </p>
        </div>
        <Link to="/app/assessment/history" className="btn-ghost shrink-0">
          <History size={15} /> History
        </Link>
      </div>

      {loading ? (
        <Card className="p-6"><LoadingBlock rows={6} /></Card>
      ) : error ? (
        <Card className="p-6"><ErrorState message={error.message} onRetry={retry} /></Card>
      ) : (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="p-6">
            <SectionHeading icon={ClipboardList} title="Configure your assessment" />
            <div className="mt-5 space-y-5">
              {/* Category */}
              <div>
                <label className="mb-2 block text-xs font-medium text-slate-400">Category</label>
                <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
                  {data.categories.map((c) => {
                    const meta = categoryMeta(c.id)
                    const active = category === c.id
                    return (
                      <button
                        key={c.id}
                        onClick={() => setCategory(c.id)}
                        className={`flex items-center gap-3 rounded-xl border p-3 text-left transition-all ${
                          active ? 'border-brand-purple/50 bg-brand-soft' : 'border-white/5 bg-ink-900/60 hover:border-white/10'
                        }`}
                      >
                        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-ink-900 text-brand-violet">
                          <meta.icon size={16} />
                        </span>
                        <span className="text-sm font-medium text-slate-100">{c.label}</span>
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Difficulty */}
              <div>
                <label className="mb-2 block text-xs font-medium text-slate-400">Difficulty</label>
                <div className="flex flex-wrap gap-2">
                  {data.difficulties.map((d) => (
                    <Pill key={d} active={difficulty === d} onClick={() => setDifficulty(d)}>
                      <span className="flex items-center gap-1.5">
                        <span className="h-2 w-2 rounded-full" style={{ background: difficultyMeta(d).hex }} />
                        {difficultyMeta(d).label}
                      </span>
                    </Pill>
                  ))}
                </div>
              </div>

              <div className="grid gap-5 sm:grid-cols-2">
                <div>
                  <label className="mb-2 flex items-center gap-1.5 text-xs font-medium text-slate-400">
                    <ListChecks size={13} /> Number of questions
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {data.question_counts.map((n) => (
                      <Pill key={n} active={numQuestions === n} onClick={() => setNumQuestions(n)}>{n}</Pill>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="mb-2 flex items-center gap-1.5 text-xs font-medium text-slate-400">
                    <Clock size={13} /> Duration (minutes)
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {data.durations_min.map((d) => (
                      <Pill key={d} active={durationMin === d} onClick={() => setDurationMin(d)}>{d}</Pill>
                    ))}
                  </div>
                </div>
              </div>

              <div className="flex items-start gap-2 rounded-xl border border-white/10 bg-white/[0.03] p-3 text-xs text-slate-400">
                <Info size={14} className="mt-0.5 shrink-0 text-brand-violet" />
                Once you start, a server-side timer begins. The assessment auto-submits when time expires.
                You can navigate between questions, mark for review, and change answers until you submit.
                Correct answers and explanations appear only after you submit.
              </div>

              {startError ? <ErrorState message={startError} /> : null}

              <button className="btn-primary !py-3" onClick={start} disabled={starting}>
                {starting ? <Spinner label="Preparing your assessment…" /> : (<>Start assessment <ArrowRight size={16} /></>)}
              </button>
            </div>
          </Card>

          <p className="mt-4 text-center text-xs text-slate-600">
            Question bank: {data.bank_stats.total} curated questions across {Object.keys(data.bank_stats.by_category).length} categories.
          </p>
        </motion.div>
      )}
    </div>
  )
}
