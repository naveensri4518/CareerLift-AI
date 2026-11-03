import { Link, useParams } from 'react-router-dom'
import { ArrowRight, CheckCircle2, Layers, RotateCcw, ThumbsUp, TriangleAlert, XCircle } from 'lucide-react'
import { motion } from 'framer-motion'
import { Badge, Card, ErrorState, LoadingBlock, SectionHeading } from '../../components/ui.jsx'
import { api } from '../../api/client.js'
import { useApi } from '../../lib/useApi.js'
import { dimensionLabel, gradeMeta } from '../../lib/sysdesign.js'

function DimensionBar({ dim, d }) {
  const pct = Math.round(d.score * 100)
  const hex = pct >= 75 ? '#34d399' : pct >= 50 ? '#fbbf24' : '#f87171'
  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm text-slate-300">{dimensionLabel(dim)}</span>
        <span className="text-xs font-semibold" style={{ color: hex }}>{pct}%</span>
      </div>
      <div className="mt-1 h-2 overflow-hidden rounded-full bg-white/5">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: hex }} />
      </div>
      {d.feedback ? <p className="mt-1.5 text-xs text-slate-500">{d.feedback}</p> : null}
      {d.missing?.length ? <p className="mt-1 text-xs text-bad">Missing: {d.missing.map((m) => Array.isArray(m) ? m.join('→') : m).join(', ')}</p> : null}
    </div>
  )
}

export default function SysDesignResult() {
  const { id } = useParams()
  const { data, loading, error, retry } = useApi((t) => api.sysdesignResult(t, id), [id])

  if (loading) return <div className="mx-auto max-w-3xl"><Card className="p-6"><LoadingBlock rows={8} /></Card></div>
  if (error) return <div className="mx-auto max-w-3xl"><Card className="p-6"><ErrorState message={error.message} onRetry={retry} /></Card></div>
  if (!data) return null

  const r = data.result
  const g = gradeMeta(r.grade)
  const labelFor = (cid) => {
    const c = (data.brief?.palette || []).find((x) => x.id === cid)
    return c ? c.label : cid
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-white">Design results</h1>
          <p className="mt-1 text-sm text-slate-400">{data.title}</p>
        </div>
        <Link to="/app/sysdesign" className="btn-ghost"><RotateCcw size={15} /> New challenge</Link>
      </div>

      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
        <Card className="flex items-center gap-5 p-6">
          <div className="grid h-24 w-24 place-items-center rounded-full border-4" style={{ borderColor: g.hex }}>
            <span className="text-3xl font-extrabold" style={{ color: g.hex }}>{r.grade}</span>
          </div>
          <div>
            <p className="text-3xl font-extrabold text-white">{r.percentage}%</p>
            <p className="text-sm text-slate-400">overall design score</p>
          </div>
        </Card>
      </motion.div>

      <Card className="p-5">
        <SectionHeading icon={Layers} title="Dimension breakdown" />
        <div className="mt-4 space-y-4">
          {Object.entries(r.dimensions).map(([dim, d]) => <DimensionBar key={dim} dim={dim} d={d} />)}
        </div>
      </Card>

      <div className="grid gap-5 sm:grid-cols-2">
        <Card className="p-5">
          <SectionHeading icon={ThumbsUp} title="Strengths" />
          <div className="mt-3 space-y-1.5">
            {r.strengths?.length ? r.strengths.map((s) => (
              <p key={s} className="flex items-center gap-2 text-sm text-good"><CheckCircle2 size={14} /> {dimensionLabel(s)}</p>
            )) : <p className="text-sm text-slate-500">No dimension reached 75% yet.</p>}
          </div>
        </Card>
        <Card className="p-5">
          <SectionHeading icon={TriangleAlert} title="Weak areas" />
          <div className="mt-3 space-y-1.5">
            {r.weaknesses?.length ? r.weaknesses.map((w) => (
              <p key={w} className="flex items-center gap-2 text-sm text-bad"><XCircle size={14} /> {dimensionLabel(w)}</p>
            )) : <p className="text-sm text-slate-500">No weak dimensions — strong design.</p>}
          </div>
        </Card>
      </div>

      <Card className="p-5">
        <SectionHeading icon={Layers} title="Expected design (reference)" />
        <div className="mt-3 space-y-2 text-sm text-slate-300">
          <p><span className="text-slate-400">Required components:</span> {data.expected.required_components.map(labelFor).join(', ') || '—'}</p>
          <p><span className="text-slate-400">Recommended:</span> {data.expected.recommended_components.map(labelFor).join(', ') || '—'}</p>
          <p><span className="text-slate-400">Key connections:</span> {data.expected.required_connections.map((c) => `${labelFor(c[0])}→${labelFor(c[1])}`).join(', ') || '—'}</p>
        </div>
      </Card>

      <Card className="p-5">
        <SectionHeading icon={ArrowRight} title="Keep improving" />
        <p className="mt-3 text-sm text-slate-400">
          These results fed your concept mastery. See your dashboard and Learning Planner for personalised next steps.
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link to="/app" className="btn-ghost">View dashboard <ArrowRight size={14} /></Link>
          <Link to="/app/sysdesign" className="btn-primary">Take another <ArrowRight size={14} /></Link>
        </div>
      </Card>
    </div>
  )
}
