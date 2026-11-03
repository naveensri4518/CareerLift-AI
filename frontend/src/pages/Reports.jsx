import { Link } from 'react-router-dom'
import { CheckCircle2, Code2, FileText, MessageSquare, Mic, ShieldCheck } from 'lucide-react'
import {
  Card,
  EmptyState,
  ErrorState,
  LoadingBlock,
  SectionHeading,
  StatCard,
} from '../components/ui.jsx'
import { api } from '../api/client.js'
import { useApi } from '../lib/useApi.js'
import { bandMeta, BANDS } from '../lib/content.js'

// Count how many scored interviews landed in each band, per axis. Derived strictly from real history.
function distribution(history, axis) {
  const counts = { Weak: 0, Partial: 0, Solid: 0, Strong: 0 }
  let assessed = 0
  for (const h of history) {
    const abst = axis === 'technical' ? h.abstained_technical : h.abstained_communication
    const band = axis === 'technical' ? h.technical_band : h.communication_band
    if (abst || !band) continue
    counts[band] = (counts[band] || 0) + 1
    assessed += 1
  }
  return { counts, assessed }
}

function DistributionCard({ icon: Icon, tint, title, history, axis }) {
  const { counts, assessed } = distribution(history, axis)
  return (
    <Card className="p-5">
      <div className="flex items-center gap-2">
        <span className="grid h-8 w-8 place-items-center rounded-lg" style={{ background: `${tint}22`, color: tint }}>
          <Icon size={16} />
        </span>
        <span className="text-sm font-semibold text-slate-200">{title}</span>
        <span className="ml-auto text-xs text-slate-500">{assessed} assessed</span>
      </div>
      <div className="mt-4 space-y-2.5">
        {assessed === 0 ? (
          <p className="text-xs text-slate-500">No assessed results on this axis yet.</p>
        ) : (
          BANDS.map((b) => {
            const meta = bandMeta(b)
            const pct = Math.round((counts[b] / assessed) * 100)
            return (
              <div key={b} className="flex items-center gap-3">
                <span className="w-16 shrink-0 text-xs" style={{ color: meta.hex }}>{b}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/5">
                  <div className="h-full rounded-full" style={{ width: `${pct}%`, background: meta.hex }} />
                </div>
                <span className="w-12 shrink-0 text-right text-xs text-slate-400">{counts[b]}</span>
              </div>
            )
          })
        )}
      </div>
    </Card>
  )
}

export default function Reports() {
  const { data, loading, error, retry } = useApi((t, id) => api.history(t, id))
  const history = data || []
  const scored = history.filter((h) => !h.abstained_technical || !h.abstained_communication)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-white">Reports</h1>
        <p className="mt-1 text-sm text-slate-400">
          A summary of your performance, with technical correctness kept separate from communication
          clarity. Everything here is computed from your actual interviews.
        </p>
      </div>

      {loading ? (
        <Card className="p-6"><LoadingBlock rows={6} /></Card>
      ) : error ? (
        <Card className="p-6"><ErrorState message={error.message} onRetry={retry} /></Card>
      ) : history.length === 0 ? (
        <Card className="p-6">
          <EmptyState
            icon={FileText}
            title="No report yet"
            hint="Complete an interview to generate your first performance summary."
            action={<Link to="/app/practice" className="btn-primary"><Mic size={15} /> Start practising</Link>}
          />
        </Card>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard
              icon={FileText}
              label="Interviews completed"
              value={history.length}
              hint="All practice interviews"
              accent="purple"
              delay={0}
            />
            <StatCard
              icon={CheckCircle2}
              label="Scored at least one axis"
              value={scored.length}
              hint="Produced a technical or communication band"
              accent="green"
              delay={0.05}
            />
            <Card className="p-4">
              <div className="flex items-center gap-2 text-good">
                <ShieldCheck size={16} />
                <p className="text-xs font-medium">Fair scoring</p>
              </div>
              <p className="mt-2 text-sm text-slate-400">
                Technical and communication are reported independently — never combined into one number.
              </p>
            </Card>
          </div>

          <div className="grid gap-5 lg:grid-cols-2">
            <DistributionCard icon={Code2} tint="#a78bfa" title="Technical band distribution" history={history} axis="technical" />
            <DistributionCard icon={MessageSquare} tint="#3b82f6" title="Communication band distribution" history={history} axis="communication" />
          </div>

          <Card className="p-5">
            <SectionHeading icon={FileText} title="What this report does not include" />
            <p className="mt-3 text-sm leading-relaxed text-slate-400">
              We only show what your interviews actually produced. We don’t invent numeric percentages,
              rankings, or predicted outcomes. Bands (Weak, Partial, Solid, Strong) are the real unit of
              assessment, and answers we couldn’t confidently judge are counted as “not assessed,” not as
              low scores.
            </p>
          </Card>
        </>
      )}
    </div>
  )
}
