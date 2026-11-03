import { Link } from 'react-router-dom'
import { ArrowRight, ClipboardList, History, TrendingUp } from 'lucide-react'
import { motion } from 'framer-motion'
import { Badge, Card, EmptyState, ErrorState, LoadingBlock, SectionHeading } from '../../components/ui.jsx'
import { api } from '../../api/client.js'
import { useApi } from '../../lib/useApi.js'
import { categoryLabel, difficultyMeta, gradeMeta } from '../../lib/assessment.js'

function statusBadge(status) {
  if (status === 'submitted') return <Badge tone="good">Completed</Badge>
  if (status === 'timed_out') return <Badge tone="warn">Timed out</Badge>
  return <Badge tone="muted">In progress</Badge>
}

export default function AssessmentHistory() {
  const { data, loading, error, retry } = useApi((t) => api.assessmentAttempts(t))
  const attempts = data?.attempts || []
  const finished = attempts.filter((a) => a.percentage != null)
  // improvement over time: oldest -> newest percentage among finished attempts (real data only)
  const trend = [...finished].reverse().map((a) => a.percentage)
  const improving = trend.length >= 2 && trend[trend.length - 1] > trend[0]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-white">Assessment history</h1>
          <p className="mt-1 text-sm text-slate-400">Your previous attempts, scores and progress over time.</p>
        </div>
        <Link to="/app/assessment" className="btn-primary shrink-0"><ClipboardList size={15} /> New assessment</Link>
      </div>

      {loading ? (
        <Card className="p-6"><LoadingBlock rows={5} /></Card>
      ) : error ? (
        <Card className="p-6"><ErrorState message={error.message} onRetry={retry} /></Card>
      ) : attempts.length === 0 ? (
        <Card className="p-6">
          <EmptyState icon={History} title="No attempts yet"
            hint="Take your first technical assessment to see your scores and track improvement here."
            action={<Link to="/app/assessment" className="btn-primary"><ClipboardList size={15} /> Start one</Link>} />
        </Card>
      ) : (
        <>
          {finished.length >= 2 ? (
            <Card className="p-5">
              <SectionHeading icon={TrendingUp} title="Improvement over time" />
              <p className="mt-3 text-sm text-slate-400">
                First completed score: <span className="font-semibold text-slate-200">{trend[0]}%</span>.
                Latest: <span className="font-semibold text-slate-200">{trend[trend.length - 1]}%</span>.
                {improving ? ' Trending up — keep it going.' : ' Keep practising to push this up.'}
              </p>
            </Card>
          ) : null}

          <Card className="p-5">
            <SectionHeading icon={History} title="Attempts" action={<Badge tone="muted">{attempts.length}</Badge>} />
            <div className="mt-4 space-y-2.5">
              {attempts.map((a, i) => {
                const g = a.grade ? gradeMeta(a.grade) : null
                const finishedAttempt = a.percentage != null
                return (
                  <motion.div key={a.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}>
                    <Link to={finishedAttempt ? `/app/assessment/result/${a.id}` : `/app/assessment/attempt/${a.id}`}
                      className="flex items-center justify-between gap-3 rounded-xl border border-white/5 bg-ink-900/50 px-4 py-3 text-sm transition-all hover:border-white/10">
                      <div className="min-w-0">
                        <p className="truncate font-medium text-slate-200">{categoryLabel(a.category)}</p>
                        <p className="mt-0.5 text-xs text-slate-500">
                          {difficultyMeta(a.difficulty).label} · {a.num_questions} questions · {new Date(a.created_at).toLocaleString()}
                        </p>
                      </div>
                      <div className="flex items-center gap-3">
                        {statusBadge(a.status)}
                        {finishedAttempt ? (
                          <span className="flex items-center gap-2">
                            <span className="text-xs text-slate-400">{a.total_score}/{a.max_score}</span>
                            <span className="grid h-8 w-8 place-items-center rounded-lg text-sm font-bold" style={{ background: `${g.hex}22`, color: g.hex }}>
                              {a.grade}
                            </span>
                          </span>
                        ) : <ArrowRight size={15} className="text-slate-500" />}
                      </div>
                    </Link>
                  </motion.div>
                )
              })}
            </div>
          </Card>
        </>
      )}
    </div>
  )
}
