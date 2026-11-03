import { Link, useParams } from 'react-router-dom'
import {
  ArrowRight, CheckCircle2, Clock, HelpCircle, RotateCcw, Target, ThumbsUp, TriangleAlert, XCircle,
} from 'lucide-react'
import { motion } from 'framer-motion'
import { Badge, Card, ErrorState, LoadingBlock, SectionHeading } from '../../components/ui.jsx'
import { api } from '../../api/client.js'
import { useApi } from '../../lib/useApi.js'
import { categoryLabel, difficultyMeta, formatClock, gradeMeta } from '../../lib/assessment.js'

function StatTile({ label, value, hint, hex }) {
  return (
    <Card className="p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-extrabold" style={{ color: hex || '#fff' }}>{value}</p>
      {hint ? <p className="mt-1 text-[11px] text-slate-500">{hint}</p> : null}
    </Card>
  )
}

function Bar({ label, score, max }) {
  const pct = max ? Math.round((score / max) * 100) : 0
  const hex = pct >= 75 ? '#34d399' : pct >= 50 ? '#fbbf24' : '#f87171'
  return (
    <div className="flex items-center gap-3">
      <span className="w-48 shrink-0 truncate text-sm text-slate-300">{label}</span>
      <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-white/5">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: hex }} />
      </div>
      <span className="w-20 shrink-0 text-right text-xs text-slate-400">{score}/{max} · {pct}%</span>
    </div>
  )
}

function ReviewItem({ q, i }) {
  const statusMeta = {
    correct: { icon: CheckCircle2, hex: '#34d399', label: 'Correct' },
    incorrect: { icon: XCircle, hex: '#f87171', label: 'Incorrect' },
    unanswered: { icon: HelpCircle, hex: '#94a3b8', label: 'Unanswered' },
  }[q.status] || { icon: HelpCircle, hex: '#94a3b8', label: q.status }
  const correctSet = q.type === 'tf' ? null : new Set(q.correct_options || [])
  const yours = q.type === 'tf' ? q.your_answer?.bool : (q.your_answer?.selected || [])

  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-semibold text-white">{i + 1}. {q.prompt}</p>
        <span className="flex shrink-0 items-center gap-1 text-xs font-semibold" style={{ color: statusMeta.hex }}>
          <statusMeta.icon size={14} /> {statusMeta.label}
        </span>
      </div>

      <div className="mt-3 space-y-1.5 text-sm">
        {q.type === 'tf' ? (
          <>
            <p className="text-slate-400">Correct answer: <span className="font-semibold text-good">{String(q.correct_bool)}</span></p>
            <p className="text-slate-400">Your answer: <span className={yours === q.correct_bool ? 'text-good' : 'text-bad'}>{yours == null ? '—' : String(yours)}</span></p>
          </>
        ) : (
          q.options.map((o) => {
            const isCorrect = correctSet.has(o.id)
            const chosen = (yours || []).includes(o.id)
            return (
              <p key={o.id} className={`flex items-center gap-2 ${isCorrect ? 'text-good' : chosen ? 'text-bad' : 'text-slate-400'}`}>
                {isCorrect ? <CheckCircle2 size={13} /> : chosen ? <XCircle size={13} /> : <span className="h-3 w-3" />}
                {o.text}{chosen ? ' (your choice)' : ''}
              </p>
            )
          })
        )}
      </div>

      {q.explanation ? (
        <p className="mt-3 rounded-xl border border-white/5 bg-ink-900/60 p-3 text-xs leading-relaxed text-slate-300">
          {q.explanation}
        </p>
      ) : null}
    </Card>
  )
}

export default function AssessmentResult() {
  const { id } = useParams()
  const { data, loading, error, retry } = useApi((t) => api.assessmentResult(t, id), [id])

  if (loading) return <div className="mx-auto max-w-4xl"><Card className="p-6"><LoadingBlock rows={8} /></Card></div>
  if (error) return <div className="mx-auto max-w-4xl"><Card className="p-6"><ErrorState message={error.message} onRetry={retry} /></Card></div>
  if (!data) return null

  const r = data.result
  const g = gradeMeta(r.grade)
  const timedOut = data.status === 'timed_out'

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-white">Assessment results</h1>
          <p className="mt-1 text-sm text-slate-400">
            {categoryLabel(data.category)} · {difficultyMeta(data.difficulty).label}
            {timedOut ? ' · auto-submitted (time expired)' : ''}
          </p>
        </div>
        <Link to="/app/assessment" className="btn-ghost"><RotateCcw size={15} /> New assessment</Link>
      </div>

      {/* headline */}
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
        <Card className="flex flex-wrap items-center justify-between gap-6 p-6">
          <div className="flex items-center gap-5">
            <div className="grid h-24 w-24 place-items-center rounded-full border-4" style={{ borderColor: g.hex }}>
              <span className="text-3xl font-extrabold" style={{ color: g.hex }}>{r.grade}</span>
            </div>
            <div>
              <p className="text-3xl font-extrabold text-white">{r.percentage}%</p>
              <p className="text-sm text-slate-400">{r.total_score} / {r.max_score} marks</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <StatTile label="Correct" value={r.correct} hex="#34d399" />
            <StatTile label="Incorrect" value={r.incorrect} hex="#f87171" />
            <StatTile label="Unanswered" value={r.unanswered} hex="#94a3b8" />
            <StatTile label="Accuracy" value={`${r.accuracy}%`} hint="of answered" />
          </div>
        </Card>
      </motion.div>

      {/* time + category/difficulty breakdown */}
      <div className="grid gap-5 lg:grid-cols-2">
        <Card className="p-5">
          <SectionHeading icon={Clock} title="Time management" />
          <div className="mt-4 space-y-2 text-sm text-slate-300">
            <p className="flex justify-between"><span className="text-slate-400">Time taken</span><span>{data.time_taken_sec != null ? formatClock(data.time_taken_sec) : '—'}</span></p>
            <p className="flex justify-between"><span className="text-slate-400">Allotted</span><span>{formatClock(data.duration_sec)}</span></p>
          </div>
        </Card>
        <Card className="p-5">
          <SectionHeading icon={Target} title="Difficulty-wise performance" />
          <div className="mt-4 space-y-3">
            {Object.entries(r.by_difficulty).map(([diff, d]) => (
              <Bar key={diff} label={difficultyMeta(diff).label} score={d.score} max={d.max} />
            ))}
          </div>
        </Card>
      </div>

      <Card className="p-5">
        <SectionHeading icon={Target} title="Category-wise performance" />
        <div className="mt-4 space-y-3">
          {Object.entries(r.by_category).map(([cat, d]) => (
            <Bar key={cat} label={categoryLabel(cat)} score={d.score} max={d.max} />
          ))}
        </div>
      </Card>

      {/* strengths / weaknesses */}
      <div className="grid gap-5 lg:grid-cols-2">
        <Card className="p-5">
          <SectionHeading icon={ThumbsUp} title="Strength areas" />
          <div className="mt-3 space-y-2">
            {r.strengths?.length ? r.strengths.map((s) => (
              <p key={s.category} className="flex items-center justify-between text-sm">
                <span className="text-slate-200">{categoryLabel(s.category)}</span>
                <span className="font-semibold text-good">{s.percentage}%</span>
              </p>
            )) : <p className="text-sm text-slate-500">No standout strengths in this attempt yet.</p>}
          </div>
        </Card>
        <Card className="p-5">
          <SectionHeading icon={TriangleAlert} title="Weak areas" />
          <div className="mt-3 space-y-2">
            {r.weaknesses?.length ? r.weaknesses.map((w) => (
              <p key={w.category} className="flex items-center justify-between text-sm">
                <span className="text-slate-200">{categoryLabel(w.category)}</span>
                <span className="font-semibold text-bad">{w.percentage}%</span>
              </p>
            )) : <p className="text-sm text-slate-500">No weak areas detected — nice work.</p>}
          </div>
        </Card>
      </div>

      {/* recommendations pointer into Phase 0 */}
      <Card className="p-5">
        <SectionHeading icon={ArrowRight} title="Keep improving" />
        <p className="mt-3 text-sm text-slate-400">
          These results fed your concept mastery and recommendations. Head to your dashboard and Learning
          Planner for personalised next steps based on everything you've practised.
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link to="/app" className="btn-ghost">View dashboard <ArrowRight size={14} /></Link>
          <Link to="/app/planner" className="btn-ghost">Learning Planner <ArrowRight size={14} /></Link>
          <Link to="/app/assessment" className="btn-primary">Take another <ArrowRight size={14} /></Link>
        </div>
      </Card>

      {/* question-by-question review */}
      <div className="space-y-4">
        <SectionHeading icon={CheckCircle2} title="Question-by-question review" action={<Badge tone="muted">{data.review.length}</Badge>} />
        {data.review.map((q, i) => <ReviewItem key={q.id} q={q} i={i} />)}
      </div>
    </div>
  )
}
