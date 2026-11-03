import { Link } from 'react-router-dom'
import { ArrowRight, CheckCircle2, History, Network } from 'lucide-react'
import { motion } from 'framer-motion'
import { Badge, Card, EmptyState, ErrorState, LoadingBlock, SectionHeading } from '../../components/ui.jsx'
import { api } from '../../api/client.js'
import { useApi } from '../../lib/useApi.js'
import { difficultyMeta } from '../../lib/sysdesign.js'

const ORDER = ['beginner', 'intermediate', 'advanced']

function ScenarioCard({ s, index }) {
  const meta = difficultyMeta(s.difficulty)
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.03 }}>
      <Link to={`/app/sysdesign/scenario/${encodeURIComponent(s.id)}`} className="group block">
        <Card className="flex h-full flex-col p-5 transition-all hover:-translate-y-0.5 hover:border-white/10">
          <div className="flex items-start justify-between gap-3">
            <h3 className="text-sm font-bold text-white">{s.title}</h3>
            {s.attempted ? (
              <span className="flex items-center gap-1 text-xs font-semibold text-good"><CheckCircle2 size={14} /> Attempted</span>
            ) : null}
          </div>
          <p className="mt-2 flex-1 text-xs leading-relaxed text-slate-400 line-clamp-3">{s.prompt}</p>
          <div className="mt-4 flex items-center justify-between">
            <span className="chip" style={{ background: `${meta.hex}22`, color: meta.hex }}>{meta.label}</span>
            <span className="flex items-center gap-1 text-xs font-medium text-brand-violet opacity-0 transition-opacity group-hover:opacity-100">
              Open <ArrowRight size={13} />
            </span>
          </div>
        </Card>
      </Link>
    </motion.div>
  )
}

export default function SysDesignAcademy() {
  const { data, loading, error, retry } = useApi((t) => api.sysdesignScenarios(t))
  const scenarios = data?.scenarios || []

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-white">System Design Academy</h1>
          <p className="mt-1 text-sm text-slate-400">
            Work through real system design challenges. Pick the components, wire them together, make the
            key database, API and scalability decisions, and get deterministic, rubric-based feedback that
            feeds your concept mastery.
          </p>
        </div>
        <Link to="/app/sysdesign/history" className="btn-ghost shrink-0"><History size={15} /> History</Link>
      </div>

      {loading ? (
        <Card className="p-6"><LoadingBlock rows={6} /></Card>
      ) : error ? (
        <Card className="p-6"><ErrorState message={error.message} onRetry={retry} /></Card>
      ) : scenarios.length === 0 ? (
        <Card className="p-6"><EmptyState icon={Network} title="No scenarios available" hint="The scenario bank is empty." /></Card>
      ) : (
        <>
          <Card className="p-4">
            <SectionHeading icon={Network} title="Challenges" action={<Badge tone="muted">{scenarios.length}</Badge>} />
          </Card>
          {ORDER.map((diff) => {
            const group = scenarios.filter((s) => s.difficulty === diff)
            if (!group.length) return null
            const meta = difficultyMeta(diff)
            return (
              <div key={diff} className="space-y-3">
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full" style={{ background: meta.hex }} />
                  <h2 className="text-sm font-semibold text-slate-200">{meta.label}</h2>
                  <Badge tone="muted">{group.length}</Badge>
                </div>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {group.map((s, i) => <ScenarioCard key={s.id} s={s} index={i} />)}
                </div>
              </div>
            )
          })}
        </>
      )}
    </div>
  )
}
