import { Link } from 'react-router-dom'
import { ArrowRight, History, Network, TrendingUp } from 'lucide-react'
import { motion } from 'framer-motion'
import { Badge, Card, EmptyState, ErrorState, LoadingBlock, SectionHeading } from '../../components/ui.jsx'
import { api } from '../../api/client.js'
import { useApi } from '../../lib/useApi.js'
import { difficultyMeta, gradeMeta } from '../../lib/sysdesign.js'

export default function SysDesignHistory() {
  const { data, loading, error, retry } = useApi((t) => api.sysdesignAttempts(t))
  const attempts = data?.attempts || []
  const finished = attempts.filter((a) => a.percentage != null)
  const trend = [...finished].reverse().map((a) => a.percentage)
  const improving = trend.length >= 2 && trend[trend.length - 1] > trend[0]

  const scenarioTitle = (sid) => sid.replace(/^SD-/, '').split('-').map((w) => w[0] + w.slice(1).toLowerCase()).join(' ')

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-white">System Design history</h1>
          <p className="mt-1 text-sm text-slate-400">Your previous challenges, scores and progress over time.</p>
        </div>
        <Link to="/app/sysdesign" className="btn-primary shrink-0"><Network size={15} /> New challenge</Link>
      </div>

      {loading ? (
        <Card className="p-6"><LoadingBlock rows={5} /></Card>
      ) : error ? (
        <Card className="p-6"><ErrorState message={error.message} onRetry={retry} /></Card>
      ) : attempts.length === 0 ? (
        <Card className="p-6">
          <EmptyState icon={History} title="No attempts yet"
            hint="Take your first system design challenge to see your scores and track improvement here."
            action={<Link to="/app/sysdesign" className="btn-primary"><Network size={15} /> Start one</Link>} />
        </Card>
      ) : (
        <>
          {finished.length >= 2 ? (
            <Card className="p-5">
              <SectionHeading icon={TrendingUp} title="Improvement over time" />
              <p className="mt-3 text-sm text-slate-400">
                First completed score: <span className="font-semibold text-slate-200">{trend[0]}%</span>.
                Latest: <span className="font-semibold text-slate-200">{trend[trend.length - 1]}%</span>.
                {improving ? ' Trending up — keep going.' : ' Keep practising to push this up.'}
              </p>
            </Card>
          ) : null}

          <Card className="p-5">
            <SectionHeading icon={History} title="Attempts" action={<Badge tone="muted">{attempts.length}</Badge>} />
            <div className="mt-4 space-y-2.5">
              {attempts.map((a, i) => {
                const g = a.grade ? gradeMeta(a.grade) : null
                const done = a.percentage != null
                return (
                  <motion.div key={a.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}>
                    <Link to={done ? `/app/sysdesign/result/${a.id}` : `/app/sysdesign/attempt/${a.id}`}
                      className="flex items-center justify-between gap-3 rounded-xl border border-white/5 bg-ink-900/50 px-4 py-3 text-sm transition-all hover:border-white/10">
                      <div className="min-w-0">
                        <p className="truncate font-medium text-slate-200">{scenarioTitle(a.scenario_id)}</p>
                        <p className="mt-0.5 text-xs text-slate-500">
                          {difficultyMeta(a.difficulty).label} · {new Date(a.created_at).toLocaleString()}
                        </p>
                      </div>
                      <div className="flex items-center gap-3">
                        <Badge tone={a.status === 'submitted' ? 'good' : 'muted'}>{a.status === 'submitted' ? 'Completed' : 'In progress'}</Badge>
                        {done ? (
                          <span className="grid h-8 w-8 place-items-center rounded-lg text-sm font-bold" style={{ background: `${g.hex}22`, color: g.hex }}>{a.grade}</span>
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
