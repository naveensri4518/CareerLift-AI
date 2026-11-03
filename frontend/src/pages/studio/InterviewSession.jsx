import { useEffect, useRef, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronLeft,
  ChevronRight,
  Info,
  Send,
} from 'lucide-react'
import { motion } from 'framer-motion'
import { Badge, Card, ErrorState, LoadingBlock, Spinner } from '../../components/ui.jsx'
import { api } from '../../api/client.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { categoryLabel } from '../../lib/studio.js'
import { SessionResults } from './SessionResults.jsx'

export default function InterviewSession() {
  const { id } = useParams()
  const { token } = useAuth()

  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [idx, setIdx] = useState(0)
  const [answers, setAnswers] = useState({}) // question_id -> text
  const [savingState, setSavingState] = useState('idle') // idle | saving | saved
  const [submitting, setSubmitting] = useState(false)
  const saveTimer = useRef(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const s = await api.studioGet(token, id)
      setSession(s)
      const seeded = {}
      for (const q of s.questions) seeded[q.question_id] = q.answer || ''
      setAnswers(seeded)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    return () => clearTimeout(saveTimer.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl">
        <Card className="p-6"><LoadingBlock rows={6} /></Card>
      </div>
    )
  }
  if (error) {
    return (
      <div className="mx-auto max-w-3xl">
        <Card className="p-6"><ErrorState message={error} onRetry={load} /></Card>
      </div>
    )
  }

  // Completed session -> results view
  if (session.status === 'completed' && session.evaluation) {
    return <SessionResults session={session} />
  }

  const questions = session.questions
  const q = questions[idx]
  const total = questions.length
  const answeredCount = questions.filter((qq) => (answers[qq.question_id] || '').trim()).length

  const setAnswer = (text) => {
    setAnswers((prev) => ({ ...prev, [q.question_id]: text }))
    setSavingState('saving')
    clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => saveDraft(q.question_id, text), 700)
  }

  const saveDraft = async (questionId, text) => {
    try {
      await api.studioSaveAnswer(token, id, questionId, text)
      setSavingState('saved')
    } catch {
      setSavingState('idle')
    }
  }

  const go = async (nextIdx) => {
    // flush current draft before navigating
    clearTimeout(saveTimer.current)
    await saveDraft(q.question_id, answers[q.question_id] || '')
    setIdx(Math.max(0, Math.min(total - 1, nextIdx)))
    setSavingState('idle')
  }

  const submit = async () => {
    setSubmitting(true)
    setError(null)
    try {
      clearTimeout(saveTimer.current)
      await saveDraft(q.question_id, answers[q.question_id] || '')
      await api.studioSubmit(token, id)
      await load() // reload -> now completed -> results view
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div className="flex items-center justify-between gap-3">
        <Link to="/app/interview" className="flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200">
          <ArrowLeft size={15} /> Studio
        </Link>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <Badge tone="muted">{categoryLabel(session.category)}</Badge>
          <Badge tone="muted">{session.difficulty}</Badge>
          <span>{answeredCount}/{total} answered</span>
        </div>
      </div>

      {/* progress bar */}
      <div className="h-1.5 overflow-hidden rounded-full bg-white/5">
        <div
          className="h-full rounded-full bg-brand-gradient transition-all"
          style={{ width: `${((idx + 1) / total) * 100}%` }}
        />
      </div>

      <motion.div key={q.question_id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
        <Card glow className="p-6">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <span className="font-semibold text-brand-violet">Question {idx + 1} of {total}</span>
            <Badge tone="muted">{q.category}</Badge>
          </div>
          <p className="mt-3 text-lg font-semibold leading-relaxed text-white">{q.text}</p>
        </Card>
      </motion.div>

      <Card className="p-6">
        <div className="mb-2 flex items-center justify-between">
          <label htmlFor="ans" className="text-sm font-semibold text-slate-200">Your answer</label>
          <span className="text-xs text-slate-500">
            {savingState === 'saving' ? 'Saving…' : savingState === 'saved' ? (
              <span className="flex items-center gap-1 text-good"><Check size={12} /> Saved</span>
            ) : ''}
          </span>
        </div>
        <textarea
          id="ans"
          className="input min-h-[180px] resize-y leading-relaxed"
          placeholder="Answer in your own words. Short, plain sentences are completely fine."
          value={answers[q.question_id] || ''}
          maxLength={8000}
          onChange={(e) => setAnswer(e.target.value)}
        />
        <p className="mt-2 flex items-center gap-1.5 text-xs text-slate-500">
          <Info size={13} /> Don’t include personal details (phone, email, id numbers).
        </p>

        {error ? <div className="mt-4"><ErrorState message={error} /></div> : null}

        <div className="mt-4 flex items-center justify-between gap-3">
          <button className="btn-ghost" onClick={() => go(idx - 1)} disabled={idx === 0}>
            <ChevronLeft size={15} /> Previous
          </button>
          {idx < total - 1 ? (
            <button className="btn-ghost" onClick={() => go(idx + 1)}>
              Next <ChevronRight size={15} />
            </button>
          ) : (
            <button className="btn-primary" onClick={submit} disabled={submitting}>
              {submitting ? <Spinner label="Evaluating…" /> : (
                <>
                  Submit interview <Send size={15} />
                </>
              )}
            </button>
          )}
        </div>
      </Card>

      {/* question dots for quick navigation */}
      <div className="flex flex-wrap items-center justify-center gap-2">
        {questions.map((qq, i) => {
          const done = (answers[qq.question_id] || '').trim()
          return (
            <button
              key={qq.question_id}
              onClick={() => go(i)}
              title={`Question ${i + 1}${done ? ' (answered)' : ''}`}
              className={`h-8 w-8 rounded-lg text-xs font-semibold transition-all ${
                i === idx
                  ? 'bg-brand-gradient text-white'
                  : done
                  ? 'bg-good/15 text-good'
                  : 'bg-white/5 text-slate-400 hover:bg-white/10'
              }`}
            >
              {i + 1}
            </button>
          )
        })}
      </div>

      <div className="text-center">
        <button className="btn-ghost" onClick={submit} disabled={submitting}>
          Submit now ({answeredCount}/{total} answered) <ArrowRight size={15} />
        </button>
      </div>
    </div>
  )
}
