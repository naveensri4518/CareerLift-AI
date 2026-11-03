import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  AlertTriangle, Check, ChevronLeft, ChevronRight, Clock, Flag, Send,
} from 'lucide-react'
import { motion } from 'framer-motion'
import { Badge, Card, ErrorState, LoadingBlock, Spinner } from '../../components/ui.jsx'
import { api } from '../../api/client.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { categoryLabel, difficultyMeta, formatClock, questionTypeLabel } from '../../lib/assessment.js'

export default function AssessmentAttempt() {
  const { id } = useParams()
  const { token } = useAuth()
  const navigate = useNavigate()

  const [attempt, setAttempt] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [idx, setIdx] = useState(0)
  const [answers, setAnswers] = useState({})     // {qid: {selected:[...]} | {bool: true}}
  const [marked, setMarked] = useState(() => new Set())  // qids marked for review (client-side aid)
  const [remaining, setRemaining] = useState(0)
  const [saving, setSaving] = useState('idle')
  const [submitting, setSubmitting] = useState(false)
  const [confirmSubmit, setConfirmSubmit] = useState(false)
  const saveTimer = useRef(null)
  const autoSubmitted = useRef(false)

  const load = async () => {
    setLoading(true); setError(null)
    try {
      const a = await api.assessmentAttempt(token, id)
      if (a.status !== 'in_progress') { navigate(`/app/assessment/result/${id}`, { replace: true }); return }
      setAttempt(a)
      setAnswers(a.answers || {})
      setRemaining(a.remaining_sec)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(); return () => clearTimeout(saveTimer.current) /* eslint-disable-line */ }, [id])

  // Local countdown off the server's remaining_sec; when it hits 0 we submit (server also enforces).
  useEffect(() => {
    if (!attempt) return
    const t = setInterval(() => setRemaining((r) => Math.max(0, r - 1)), 1000)
    return () => clearInterval(t)
  }, [attempt])

  useEffect(() => {
    if (attempt && remaining <= 0 && !autoSubmitted.current) {
      autoSubmitted.current = true
      doSubmit(true)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [remaining, attempt])

  const questions = attempt?.questions || []
  const q = questions[idx]
  const total = questions.length

  const answeredCount = useMemo(
    () => questions.filter((qq) => {
      const a = answers[qq.id]
      return a && (a.bool != null || (a.selected && a.selected.length))
    }).length,
    [questions, answers],
  )

  const persist = async (next) => {
    setSaving('saving')
    try { await api.assessmentSaveAnswers(token, id, next); setSaving('saved') }
    catch { setSaving('idle') }
  }

  const scheduleSave = (next) => {
    clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => persist(next), 500)
  }

  const setSingle = (optId) => {
    const next = { ...answers, [q.id]: { selected: [optId] } }
    setAnswers(next); scheduleSave(next)
  }
  const toggleMulti = (optId) => {
    const cur = new Set(answers[q.id]?.selected || [])
    cur.has(optId) ? cur.delete(optId) : cur.add(optId)
    const next = { ...answers, [q.id]: { selected: [...cur] } }
    setAnswers(next); scheduleSave(next)
  }
  const setBool = (val) => {
    const next = { ...answers, [q.id]: { bool: val } }
    setAnswers(next); scheduleSave(next)
  }

  const toggleMark = () => {
    setMarked((m) => { const n = new Set(m); n.has(q.id) ? n.delete(q.id) : n.add(q.id); return n })
  }

  const go = (to) => { clearTimeout(saveTimer.current); persist(answers); setIdx(Math.max(0, Math.min(total - 1, to))) }

  const doSubmit = async (auto = false) => {
    setSubmitting(true)
    try {
      clearTimeout(saveTimer.current)
      if (!auto) await persist(answers)
      await api.assessmentSubmit(token, id)
      navigate(`/app/assessment/result/${id}`, { replace: true })
    } catch (err) {
      setError(err.message); setSubmitting(false)
    }
  }

  if (loading) return <div className="mx-auto max-w-5xl"><Card className="p-6"><LoadingBlock rows={8} /></Card></div>
  if (error) return <div className="mx-auto max-w-5xl"><Card className="p-6"><ErrorState message={error} onRetry={load} /></Card></div>
  if (!q) return null

  const myAns = answers[q.id] || {}
  const low = remaining <= 60

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      {/* header: meta + timer */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Badge tone="muted">{categoryLabel(attempt.category)}</Badge>
          <span className="chip" style={{ background: `${difficultyMeta(attempt.difficulty).hex}22`, color: difficultyMeta(attempt.difficulty).hex }}>
            {difficultyMeta(attempt.difficulty).label}
          </span>
        </div>
        <div className={`flex items-center gap-2 rounded-xl border px-3.5 py-2 text-sm font-semibold ${
          low ? 'border-bad/40 bg-bad/10 text-bad' : 'border-white/10 bg-white/5 text-slate-200'
        }`}>
          <Clock size={15} /> {formatClock(remaining)}
        </div>
      </div>

      {/* progress bar */}
      <div className="h-1.5 overflow-hidden rounded-full bg-white/5">
        <div className="h-full rounded-full bg-brand-gradient transition-all" style={{ width: `${((idx + 1) / total) * 100}%` }} />
      </div>

      <div className="grid gap-5 lg:grid-cols-[1fr,260px]">
        {/* question */}
        <div className="space-y-4">
          <motion.div key={q.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
            <Card glow className="p-6">
              <div className="flex items-center justify-between gap-2 text-xs text-slate-500">
                <span className="font-semibold text-brand-violet">Question {idx + 1} of {total}</span>
                <span>{questionTypeLabel(q.type)} · {q.marks} mark{q.marks > 1 ? 's' : ''}</span>
              </div>
              <p className="mt-3 text-lg font-semibold leading-relaxed text-white">{q.prompt}</p>

              <div className="mt-5 space-y-2.5">
                {q.type === 'tf' ? (
                  [{ v: true, t: 'True' }, { v: false, t: 'False' }].map((o) => {
                    const sel = myAns.bool === o.v
                    return (
                      <button key={o.t} onClick={() => setBool(o.v)}
                        className={`flex w-full items-center gap-3 rounded-xl border p-3.5 text-left text-sm transition-all ${
                          sel ? 'border-brand-purple/50 bg-brand-soft text-white' : 'border-white/5 bg-ink-900/60 text-slate-200 hover:border-white/10'
                        }`}>
                        <span className={`grid h-5 w-5 shrink-0 place-items-center rounded-full border ${sel ? 'border-brand-violet bg-brand-violet text-white' : 'border-white/20'}`}>
                          {sel ? <Check size={12} /> : null}
                        </span>
                        {o.t}
                      </button>
                    )
                  })
                ) : (
                  q.options.map((o) => {
                    const sel = (myAns.selected || []).includes(o.id)
                    const multi = q.type === 'multi'
                    return (
                      <button key={o.id} onClick={() => (multi ? toggleMulti(o.id) : setSingle(o.id))}
                        className={`flex w-full items-center gap-3 rounded-xl border p-3.5 text-left text-sm transition-all ${
                          sel ? 'border-brand-purple/50 bg-brand-soft text-white' : 'border-white/5 bg-ink-900/60 text-slate-200 hover:border-white/10'
                        }`}>
                        <span className={`grid h-5 w-5 shrink-0 place-items-center border ${multi ? 'rounded-md' : 'rounded-full'} ${sel ? 'border-brand-violet bg-brand-violet text-white' : 'border-white/20'}`}>
                          {sel ? <Check size={12} /> : null}
                        </span>
                        {o.text}
                      </button>
                    )
                  })
                )}
              </div>
              {q.type === 'multi' ? <p className="mt-3 text-xs text-slate-500">Select all that apply — an exact match is required for marks.</p> : null}
            </Card>
          </motion.div>

          <div className="flex items-center justify-between gap-3">
            <button className="btn-ghost" onClick={() => go(idx - 1)} disabled={idx === 0}><ChevronLeft size={15} /> Previous</button>
            <button className={`btn-ghost ${marked.has(q.id) ? '!text-warn !border-warn/40' : ''}`} onClick={toggleMark}>
              <Flag size={14} /> {marked.has(q.id) ? 'Marked' : 'Mark for review'}
            </button>
            {idx < total - 1 ? (
              <button className="btn-ghost" onClick={() => go(idx + 1)}>Next <ChevronRight size={15} /></button>
            ) : (
              <button className="btn-primary" onClick={() => setConfirmSubmit(true)}>Finish <Send size={15} /></button>
            )}
          </div>
          <p className="text-center text-xs text-slate-500">
            {saving === 'saving' ? 'Saving…' : saving === 'saved' ? 'Answers saved' : ''}
          </p>
        </div>

        {/* navigation panel */}
        <Card className="h-fit p-4">
          <p className="text-sm font-semibold text-slate-200">Questions</p>
          <p className="mt-1 text-xs text-slate-500">{answeredCount}/{total} answered</p>
          <div className="mt-3 grid grid-cols-5 gap-2">
            {questions.map((qq, i) => {
              const a = answers[qq.id]
              const answered = a && (a.bool != null || (a.selected && a.selected.length))
              const isMarked = marked.has(qq.id)
              return (
                <button key={qq.id} onClick={() => go(i)} title={`Question ${i + 1}`}
                  className={`relative grid h-9 place-items-center rounded-lg text-xs font-semibold transition-all ${
                    i === idx ? 'bg-brand-gradient text-white' : answered ? 'bg-good/15 text-good' : 'bg-white/5 text-slate-400 hover:bg-white/10'
                  }`}>
                  {i + 1}
                  {isMarked ? <span className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full bg-warn" /> : null}
                </button>
              )
            })}
          </div>
          <div className="mt-4 space-y-1.5 text-xs text-slate-500">
            <p className="flex items-center gap-2"><span className="h-3 w-3 rounded bg-good/15" /> Answered</p>
            <p className="flex items-center gap-2"><span className="h-3 w-3 rounded bg-white/5" /> Unanswered</p>
            <p className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-warn" /> Marked for review</p>
          </div>
          <button className="btn-primary mt-4 w-full" onClick={() => setConfirmSubmit(true)}>Submit assessment</button>
        </Card>
      </div>

      {/* submit confirmation */}
      {confirmSubmit ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4" onClick={() => !submitting && setConfirmSubmit(false)}>
          <Card className="w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start gap-3">
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-warn/15 text-warn"><AlertTriangle size={18} /></span>
              <div>
                <h3 className="text-sm font-bold text-white">Submit your assessment?</h3>
                <p className="mt-1 text-sm text-slate-400">
                  You answered {answeredCount} of {total} questions.
                  {answeredCount < total ? ` ${total - answeredCount} will be counted as unanswered.` : ''} You cannot change answers after submitting.
                </p>
              </div>
            </div>
            <div className="mt-5 flex justify-end gap-3">
              <button className="btn-ghost" onClick={() => setConfirmSubmit(false)} disabled={submitting}>Keep going</button>
              <button className="btn-primary" onClick={() => doSubmit(false)} disabled={submitting}>
                {submitting ? <Spinner label="Submitting…" /> : (<>Submit now <Send size={15} /></>)}
              </button>
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  )
}
