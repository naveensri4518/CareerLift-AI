import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  ArrowRight,
  Code2,
  Info,
  Lightbulb,
  MessageSquare,
  Mic,
  Quote,
  RotateCcw,
  Send,
  ShieldAlert,
} from 'lucide-react'
import { motion } from 'framer-motion'
import { Badge, Card, ErrorState, SectionHeading, Spinner } from '../components/ui.jsx'
import { api } from '../api/client.js'
import { useAuth } from '../context/AuthContext.jsx'
import { bandMeta, LEVELS, TOPICS, topicLabel } from '../lib/content.js'

const STEP = { SETUP: 'setup', QUESTION: 'question', RESULT: 'result' }

function ScorePanel({ icon: Icon, tint, title, band, abstained, evidence }) {
  const meta = bandMeta(band)
  return (
    <Card className="p-5">
      <div className="flex items-center gap-2">
        <span className="grid h-8 w-8 place-items-center rounded-lg" style={{ background: `${tint}22`, color: tint }}>
          <Icon size={16} />
        </span>
        <span className="text-sm font-semibold text-slate-200">{title}</span>
        <span className="ml-auto text-lg font-extrabold" style={{ color: abstained ? '#64748b' : meta.hex }}>
          {abstained ? 'Not assessed' : band}
        </span>
      </div>
      <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-white/5">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${abstained ? 0 : meta.pct}%`, background: meta.hex }}
        />
      </div>
      {evidence?.length ? (
        <div className="mt-4 space-y-2">
          <p className="text-xs font-medium text-slate-400">From your answer:</p>
          {evidence.map((e, i) => (
            <div key={i} className="flex items-start gap-2 rounded-lg border border-white/5 bg-ink-900/60 p-2.5 text-xs text-slate-300">
              <Quote size={13} className="mt-0.5 shrink-0 text-slate-500" />
              <span className="italic">“{e}”</span>
            </div>
          ))}
        </div>
      ) : null}
    </Card>
  )
}

export default function Practice() {
  const { token } = useAuth()
  const location = useLocation()

  const [topic, setTopic] = useState(TOPICS[0].id)
  const [level, setLevel] = useState(LEVELS[0].id)

  const [step, setStep] = useState(STEP.SETUP)
  const [starting, setStarting] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  const [interview, setInterview] = useState(null) // { interview_id, question, topic, difficulty }
  const [answer, setAnswer] = useState('')
  const [result, setResult] = useState(null) // ScoreResponse

  // If the Learning Planner pre-started an interview, jump straight into the question step.
  useEffect(() => {
    const pre = location.state?.prestarted
    if (pre && !interview) {
      setInterview(pre)
      setStep(STEP.QUESTION)
      // clear router state so a refresh doesn't re-trigger
      window.history.replaceState({}, '')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state])

  const startInterview = async () => {
    setStarting(true)
    setError(null)
    try {
      const iv = await api.startInterview(token, { topic, level })
      setInterview(iv)
      setAnswer('')
      setResult(null)
      setStep(STEP.QUESTION)
    } catch (err) {
      setError(err.message)
    } finally {
      setStarting(false)
    }
  }

  const submitAnswer = async () => {
    if (!answer.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      const res = await api.scoreAnswer(token, {
        interviewId: interview.interview_id,
        question: interview.question,
        answer: answer.trim(),
      })
      setResult(res)
      setStep(STEP.RESULT)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const reset = () => {
    setStep(STEP.SETUP)
    setInterview(null)
    setAnswer('')
    setResult(null)
    setError(null)
  }

  const fullAbstain = result && result.abstained_technical && result.abstained_communication

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-white">Practice Interview</h1>
        <p className="mt-1 text-sm text-slate-400">
          Answer in your own words. Your technical understanding and your communication are scored
          separately — plain English never lowers your technical result.
        </p>
      </div>

      {/* Step 1: setup */}
      {step === STEP.SETUP && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="p-6">
            <SectionHeading icon={Mic} title="Set up your interview" />
            <div className="mt-5 space-y-5">
              <div>
                <label className="mb-2 block text-xs font-medium text-slate-400">Topic</label>
                <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
                  {TOPICS.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => setTopic(t.id)}
                      className={`rounded-xl border p-3 text-left transition-all ${
                        topic === t.id
                          ? 'border-brand-purple/50 bg-brand-soft'
                          : 'border-white/5 bg-ink-900/60 hover:border-white/10'
                      }`}
                    >
                      <p className="text-sm font-semibold text-slate-100">{t.label}</p>
                      <p className="mt-0.5 text-xs text-slate-500">{t.blurb}</p>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="mb-2 block text-xs font-medium text-slate-400">Difficulty</label>
                <div className="flex flex-wrap gap-2">
                  {LEVELS.map((l) => (
                    <button
                      key={l.id}
                      onClick={() => setLevel(l.id)}
                      className={`rounded-xl border px-4 py-2 text-sm transition-all ${
                        level === l.id
                          ? 'border-brand-purple/50 bg-brand-soft text-white'
                          : 'border-white/5 bg-ink-900/60 text-slate-300 hover:border-white/10'
                      }`}
                    >
                      {l.label}
                    </button>
                  ))}
                </div>
              </div>

              {error ? <ErrorState message={error} onRetry={startInterview} /> : null}

              <button className="btn-primary !py-3" onClick={startInterview} disabled={starting}>
                {starting ? <Spinner label="Preparing your question…" /> : (
                  <>
                    Start interview <ArrowRight size={16} />
                  </>
                )}
              </button>
            </div>
          </Card>
        </motion.div>
      )}

      {/* Step 2: question + answer */}
      {step === STEP.QUESTION && interview && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
          <Card glow className="p-6">
            <div className="flex items-center gap-2">
              <Badge tone="muted">{topicLabel(interview.topic)}</Badge>
              <Badge tone="muted">{interview.difficulty}</Badge>
            </div>
            <p className="mt-4 text-lg font-semibold leading-relaxed text-white">{interview.question}</p>
          </Card>

          <Card className="p-6">
            <label htmlFor="answer" className="mb-2 block text-sm font-semibold text-slate-200">
              Your answer
            </label>
            <textarea
              id="answer"
              className="input min-h-[180px] resize-y leading-relaxed"
              placeholder="Explain in your own words. Short, plain sentences are completely fine."
              value={answer}
              maxLength={8000}
              onChange={(e) => setAnswer(e.target.value)}
              autoFocus
            />
            <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
              <span className="flex items-center gap-1.5">
                <Info size={13} /> Don’t include personal details (phone, email, id numbers).
              </span>
              <span>{answer.length}/8000</span>
            </div>

            {error ? <div className="mt-4"><ErrorState message={error} /></div> : null}

            <div className="mt-4 flex flex-wrap gap-3">
              <button className="btn-primary !py-3" onClick={submitAnswer} disabled={submitting || !answer.trim()}>
                {submitting ? <Spinner label="Evaluating your answer…" /> : (
                  <>
                    Submit for scoring <Send size={15} />
                  </>
                )}
              </button>
              <button className="btn-ghost !py-3" onClick={reset} disabled={submitting}>
                Cancel
              </button>
            </div>
          </Card>
        </motion.div>
      )}

      {/* Step 3: result */}
      {step === STEP.RESULT && result && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
          {result.mock ? (
            <div className="flex items-center gap-2 rounded-xl border border-brand-purple/30 bg-brand-soft px-4 py-2.5 text-xs font-medium text-brand-violet">
              <Info size={14} />
              Local demo mode — this result is from a deterministic offline evaluator, not a live AI model.
            </div>
          ) : null}
          {fullAbstain ? (
            <Card className="border-warn/25 bg-warn/5 p-6">
              <div className="flex items-start gap-3">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-warn/15 text-warn">
                  <ShieldAlert size={18} />
                </span>
                <div>
                  <h3 className="text-sm font-bold text-warn">We couldn’t confidently score this answer</h3>
                  <p className="mt-1 text-sm leading-relaxed text-slate-300">
                    {result.message ||
                      'There wasn’t enough in the answer to assess it fairly. This is not a low score — it just means we won’t guess. Try explaining the core idea again in your own words.'}
                  </p>
                </div>
              </div>
            </Card>
          ) : (
            <div className="grid gap-5 sm:grid-cols-2">
              <ScorePanel
                icon={Code2}
                tint="#a78bfa"
                title="Technical"
                band={result.technical_band}
                abstained={result.abstained_technical}
                evidence={result.technical_evidence}
              />
              <ScorePanel
                icon={MessageSquare}
                tint="#3b82f6"
                title="Communication"
                band={result.communication_band}
                abstained={result.abstained_communication}
                evidence={result.communication_evidence}
              />
            </div>
          )}

          {!fullAbstain && result.message ? (
            <Card className="p-4">
              <p className="flex items-start gap-2 text-sm text-slate-300">
                <Lightbulb size={16} className="mt-0.5 shrink-0 text-brand-violet" />
                {result.message}
              </p>
            </Card>
          ) : null}

          <div className="flex flex-wrap gap-3">
            <button className="btn-primary !py-3" onClick={reset}>
              <RotateCcw size={15} /> Practise another
            </button>
            <Link to="/app/progress" className="btn-ghost !py-3">
              See my progress <ArrowRight size={15} />
            </Link>
          </div>
        </motion.div>
      )}
    </div>
  )
}
