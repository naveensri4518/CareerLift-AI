import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Boxes, ListChecks, Play } from 'lucide-react'
import { motion } from 'framer-motion'
import { Card, ErrorState, LoadingBlock, SectionHeading, Spinner } from '../../components/ui.jsx'
import { api } from '../../api/client.js'
import { useApi } from '../../lib/useApi.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { componentIcon, difficultyMeta } from '../../lib/sysdesign.js'

export default function SysDesignScenario() {
  const { id } = useParams()
  const { token } = useAuth()
  const navigate = useNavigate()
  const { data: s, loading, error, retry } = useApi((t) => api.sysdesignScenario(t, id), [id])
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState(null)

  const start = async () => {
    setStarting(true); setStartError(null)
    try {
      const res = await api.sysdesignStart(token, id)
      navigate(`/app/sysdesign/attempt/${res.attempt_id}`)
    } catch (err) { setStartError(err.message); setStarting(false) }
  }

  if (loading) return <div className="mx-auto max-w-3xl"><Card className="p-6"><LoadingBlock rows={8} /></Card></div>
  if (error) return <div className="mx-auto max-w-3xl"><Card className="p-6"><ErrorState message={error.message} onRetry={retry} /></Card></div>
  if (!s) return null
  const meta = difficultyMeta(s.difficulty)

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <Link to="/app/sysdesign" className="flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200">
        <ArrowLeft size={15} /> System Design Academy
      </Link>

      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
        <Card glow className="p-6">
          <div className="flex items-center gap-2">
            <span className="chip" style={{ background: `${meta.hex}22`, color: meta.hex }}>{meta.label}</span>
          </div>
          <h1 className="mt-3 text-xl font-extrabold text-white">{s.title}</h1>
          <p className="mt-3 text-sm leading-relaxed text-slate-300">{s.prompt}</p>
        </Card>
      </motion.div>

      <div className="grid gap-5 sm:grid-cols-2">
        <Card className="p-5">
          <SectionHeading icon={ListChecks} title="Functional requirements" />
          <ul className="mt-3 list-inside list-disc space-y-1 text-sm text-slate-300">
            {s.functional_requirements.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        </Card>
        <Card className="p-5">
          <SectionHeading icon={ListChecks} title="Non-functional requirements" />
          <ul className="mt-3 list-inside list-disc space-y-1 text-sm text-slate-300">
            {s.nonfunctional_requirements.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        </Card>
      </div>

      <Card className="p-5">
        <SectionHeading icon={Boxes} title="Available components" />
        <div className="mt-3 flex flex-wrap gap-2">
          {s.palette.map((c) => {
            const Icon = componentIcon(c.id)
            return (
              <span key={c.id} className="flex items-center gap-1.5 rounded-lg border border-white/5 bg-ink-900/60 px-2.5 py-1.5 text-xs text-slate-300">
                <Icon size={13} className="text-brand-violet" /> {c.label}
              </span>
            )
          })}
        </div>
      </Card>

      {startError ? <ErrorState message={startError} /> : null}
      <div className="flex flex-wrap gap-3">
        <button className="btn-primary !py-3" onClick={start} disabled={starting}>
          {starting ? <Spinner label="Starting…" /> : (<>Start challenge <Play size={15} /></>)}
        </button>
        <Link to="/app/sysdesign" className="btn-ghost !py-3">Choose another <ArrowRight size={15} /></Link>
      </div>
    </div>
  )
}
