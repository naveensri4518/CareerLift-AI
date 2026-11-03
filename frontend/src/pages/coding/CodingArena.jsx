import { Link } from 'react-router-dom'
import { ArrowRight, CheckCircle2, Code2, ShieldAlert } from 'lucide-react'
import { motion } from 'framer-motion'
import { Badge, Card, EmptyState, ErrorState, LoadingBlock, SectionHeading } from '../../components/ui.jsx'
import { api } from '../../api/client.js'
import { useApi } from '../../lib/useApi.js'
import { difficultyMeta, DIFFICULTY_ORDER } from '../../lib/coding.js'

// Honest sandbox banner: the arena executes code in an isolated Docker sandbox. If the sandbox is not
// available (daemon down / image not built) we say so plainly rather than pretending code can run.
function SandboxBanner() {
  const { data } = useApi((t) => api.codingStatus(t))
  if (!data || data.sandbox_available) return null
  return (
    <div className="flex items-start gap-2 rounded-xl border border-warn/25 bg-warn/5 px-4 py-3 text-xs text-warn">
      <ShieldAlert size={15} className="mt-0.5 shrink-0" />
      <span>
        The secure code sandbox is not running, so Run/Submit are disabled. {data.reason} You can still
        browse problems. Start Docker and build the sandbox image to enable execution.
      </span>
    </div>
  )
}

function ProblemCard({ problem, index }) {
  const meta = difficultyMeta(problem.difficulty)
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.03 }}
    >
      <Link to={`/app/coding/${encodeURIComponent(problem.id)}`} className="group block">
        <Card className="flex h-full flex-col p-5 transition-all hover:-translate-y-0.5 hover:border-white/10">
          <div className="flex items-start justify-between gap-3">
            <h3 className="text-sm font-bold text-white">{problem.title}</h3>
            {problem.solved ? (
              <span className="flex items-center gap-1 text-xs font-semibold text-good">
                <CheckCircle2 size={14} /> Solved
              </span>
            ) : null}
          </div>
          <div className="mt-3 flex items-center gap-2">
            <span
              className="chip"
              style={{ background: `${meta.hex}22`, color: meta.hex }}
            >
              {meta.label}
            </span>
          </div>
          <div className="mt-4 flex items-center gap-1 text-xs font-medium text-brand-violet opacity-0 transition-opacity group-hover:opacity-100">
            Open problem <ArrowRight size={13} />
          </div>
        </Card>
      </Link>
    </motion.div>
  )
}

function DifficultyGroup({ difficulty, problems }) {
  const meta = difficultyMeta(difficulty)
  if (!problems.length) return null
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-full" style={{ background: meta.hex }} />
        <h2 className="text-sm font-semibold text-slate-200">{meta.label}</h2>
        <Badge tone="muted">{problems.length}</Badge>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {problems.map((p, i) => (
          <ProblemCard key={p.id} problem={p} index={i} />
        ))}
      </div>
    </div>
  )
}

export default function CodingArena() {
  const { data, loading, error, retry } = useApi((t) => api.codingProblems(t))
  const problems = data?.problems || []
  const solvedCount = problems.filter((p) => p.solved).length

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-white">Coding Arena</h1>
        <p className="mt-1 text-sm text-slate-400">
          Solve problems in Python, C++ or Java. Your code runs in an isolated sandbox against public and
          hidden tests, and each solved problem strengthens your real concept mastery.
        </p>
      </div>

      <SandboxBanner />

      {loading ? (
        <Card className="p-6"><LoadingBlock rows={6} /></Card>
      ) : error ? (
        <Card className="p-6"><ErrorState message={error.message} onRetry={retry} /></Card>
      ) : problems.length === 0 ? (
        <Card className="p-6">
          <EmptyState icon={Code2} title="No problems available" hint="The problem bank is empty." />
        </Card>
      ) : (
        <>
          <Card className="p-4">
            <SectionHeading
              icon={Code2}
              title="Problem bank"
              action={<Badge tone={solvedCount ? 'good' : 'muted'}>{solvedCount}/{problems.length} solved</Badge>}
            />
          </Card>
          {DIFFICULTY_ORDER.map((d) => (
            <DifficultyGroup key={d} difficulty={d} problems={problems.filter((p) => p.difficulty === d)} />
          ))}
        </>
      )}
    </div>
  )
}
