import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { ArrowRight, History, Mic } from 'lucide-react'
import { motion } from 'framer-motion'
import { Card, ErrorState, SectionHeading, Spinner, Badge } from '../../components/ui.jsx'
import { api } from '../../api/client.js'
import { useApi } from '../../lib/useApi.js'
import { useAuth } from '../../context/AuthContext.jsx'
import {
  CATEGORIES,
  DIFFICULTIES,
  DURATIONS,
  EXPERIENCE,
  QUESTION_COUNTS,
  TECH_TOPICS,
  categoryLabel,
} from '../../lib/studio.js'

function Pill({ active, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-xl border px-3.5 py-2 text-sm transition-all ${
        active
          ? 'border-brand-purple/50 bg-brand-soft text-white'
          : 'border-white/5 bg-ink-900/60 text-slate-300 hover:border-white/10'
      }`}
    >
      {children}
    </button>
  )
}

function PastSessions() {
  const { data, loading, error } = useApi((t) => api.studioList(t))
  const sessions = data?.sessions || []
  if (loading) return <Spinner label="Loading history…" />
  if (error) return null
  if (!sessions.length) return null
  return (
    <Card className="p-5">
      <SectionHeading icon={History} title="Recent sessions" />
      <div className="mt-4 space-y-2">
        {sessions.slice(0, 6).map((s) => (
          <Link
            key={s.id}
            to={`/app/interview/session/${s.id}`}
            className="flex items-center justify-between rounded-xl border border-white/5 bg-ink-900/50 px-3.5 py-2.5 text-sm hover:border-white/10"
          >
            <span className="text-slate-200">
              {categoryLabel(s.category)} · {s.num_questions} questions
            </span>
            <Badge tone={s.status === 'completed' ? 'good' : 'warn'}>
              {s.status === 'completed' ? 'completed' : 'in progress'}
            </Badge>
          </Link>
        ))}
      </div>
    </Card>
  )
}

export default function InterviewStudio() {
  const { token } = useAuth()
  const navigate = useNavigate()

  const [category, setCategory] = useState('technical')
  const [difficulty, setDifficulty] = useState('beginner')
  const [experience, setExperience] = useState('student')
  const [numQuestions, setNumQuestions] = useState(5)
  const [duration, setDuration] = useState(20)
  const [topics, setTopics] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const showTopics = category === 'technical' || category === 'mixed'

  const toggleTopic = (id) =>
    setTopics((prev) => (prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]))

  const start = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.studioCreate(token, {
        category,
        difficulty,
        experience,
        duration_min: duration,
        num_questions: numQuestions,
        topics: showTopics ? topics : [],
      })
      navigate(`/app/interview/session/${res.session_id}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-white">Interview Studio</h1>
        <p className="mt-1 text-sm text-slate-400">
          Configure a realistic mock interview. Your technical understanding and your communication are
          scored separately — simple English never lowers your technical result.
        </p>
      </div>

      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
        <Card className="p-6">
          <SectionHeading icon={Mic} title="Configure your interview" />
          <div className="mt-5 space-y-5">
            {/* Category */}
            <div>
              <label className="mb-2 block text-xs font-medium text-slate-400">Category</label>
              <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
                {CATEGORIES.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => setCategory(c.id)}
                    className={`flex items-start gap-3 rounded-xl border p-3 text-left transition-all ${
                      category === c.id
                        ? 'border-brand-purple/50 bg-brand-soft'
                        : 'border-white/5 bg-ink-900/60 hover:border-white/10'
                    }`}
                  >
                    <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-ink-900 text-brand-violet">
                      <c.icon size={16} />
                    </span>
                    <span>
                      <span className="block text-sm font-semibold text-slate-100">{c.label}</span>
                      <span className="block text-xs text-slate-500">{c.blurb}</span>
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {/* Difficulty + experience */}
            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <label className="mb-2 block text-xs font-medium text-slate-400">Difficulty</label>
                <div className="flex flex-wrap gap-2">
                  {DIFFICULTIES.map((d) => (
                    <Pill key={d.id} active={difficulty === d.id} onClick={() => setDifficulty(d.id)}>
                      {d.label}
                    </Pill>
                  ))}
                </div>
              </div>
              <div>
                <label className="mb-2 block text-xs font-medium text-slate-400">Experience level</label>
                <div className="flex flex-wrap gap-2">
                  {EXPERIENCE.map((e) => (
                    <Pill key={e.id} active={experience === e.id} onClick={() => setExperience(e.id)}>
                      {e.label}
                    </Pill>
                  ))}
                </div>
              </div>
            </div>

            {/* Questions + duration */}
            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <label className="mb-2 block text-xs font-medium text-slate-400">Number of questions</label>
                <div className="flex flex-wrap gap-2">
                  {QUESTION_COUNTS.map((n) => (
                    <Pill key={n} active={numQuestions === n} onClick={() => setNumQuestions(n)}>
                      {n}
                    </Pill>
                  ))}
                </div>
              </div>
              <div>
                <label className="mb-2 block text-xs font-medium text-slate-400">Duration (minutes)</label>
                <div className="flex flex-wrap gap-2">
                  {DURATIONS.map((d) => (
                    <Pill key={d} active={duration === d} onClick={() => setDuration(d)}>
                      {d}
                    </Pill>
                  ))}
                </div>
              </div>
            </div>

            {/* Topics (technical/mixed only) */}
            {showTopics && (
              <div>
                <label className="mb-2 block text-xs font-medium text-slate-400">
                  Technical topics <span className="text-slate-600">(optional — leave empty for all)</span>
                </label>
                <div className="flex flex-wrap gap-2">
                  {TECH_TOPICS.map((t) => (
                    <Pill key={t.id} active={topics.includes(t.id)} onClick={() => toggleTopic(t.id)}>
                      {t.label}
                    </Pill>
                  ))}
                </div>
              </div>
            )}

            {error ? <ErrorState message={error} onRetry={start} /> : null}

            <button className="btn-primary !py-3" onClick={start} disabled={loading}>
              {loading ? <Spinner label="Preparing your interview…" /> : (
                <>
                  Start interview <ArrowRight size={16} />
                </>
              )}
            </button>
          </div>
        </Card>
      </motion.div>

      <PastSessions />
    </div>
  )
}
