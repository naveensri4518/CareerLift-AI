import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { ArrowLeft, Check, Link2, Plus, Send, Trash2, X } from 'lucide-react'
import { motion } from 'framer-motion'
import { Badge, Card, ErrorState, LoadingBlock, SectionHeading, Spinner } from '../../components/ui.jsx'
import { api } from '../../api/client.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { componentIcon, difficultyMeta } from '../../lib/sysdesign.js'

export default function SysDesignWorkspace() {
  const { id } = useParams()
  const { token } = useAuth()
  const navigate = useNavigate()

  const [attempt, setAttempt] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [components, setComponents] = useState([])     // [componentId]
  const [connections, setConnections] = useState([])   // [[from,to]]
  const [decisions, setDecisions] = useState({})       // {promptId: {selected:[...]}}
  const [connFrom, setConnFrom] = useState('')
  const [connTo, setConnTo] = useState('')
  const [saving, setSaving] = useState('idle')
  const [submitting, setSubmitting] = useState(false)
  const [confirm, setConfirm] = useState(false)
  const saveTimer = useRef(null)

  const load = async () => {
    setLoading(true); setError(null)
    try {
      const a = await api.sysdesignAttempt(token, id)
      if (a.status !== 'in_progress') { navigate(`/app/sysdesign/result/${id}`, { replace: true }); return }
      setAttempt(a)
      const d = a.design || {}
      setComponents(d.components || [])
      setConnections((d.connections || []).map((c) => [c[0], c[1]]))
      setDecisions(d.decisions || {})
    } catch (err) { setError(err.message) } finally { setLoading(false) }
  }
  useEffect(() => { load(); return () => clearTimeout(saveTimer.current) /* eslint-disable-line */ }, [id])

  const brief = attempt?.brief
  const palette = brief?.palette || []
  const paletteById = useMemo(() => Object.fromEntries(palette.map((c) => [c.id, c])), [palette])

  const persist = async (next) => {
    setSaving('saving')
    try { await api.sysdesignSaveDesign(token, id, next); setSaving('saved') }
    catch { setSaving('idle') }
  }
  const scheduleSave = (comps, conns, decs) => {
    const next = { components: comps, connections: conns, decisions: decs }
    clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => persist(next), 500)
  }

  const addComponent = (cid) => {
    if (components.includes(cid)) return
    const next = [...components, cid]; setComponents(next); scheduleSave(next, connections, decisions)
  }
  const removeComponent = (cid) => {
    const next = components.filter((c) => c !== cid)
    const nextConns = connections.filter((c) => c[0] !== cid && c[1] !== cid)
    setComponents(next); setConnections(nextConns); scheduleSave(next, nextConns, decisions)
  }
  const addConnection = () => {
    if (!connFrom || !connTo || connFrom === connTo) return
    if (connections.some((c) => (c[0] === connFrom && c[1] === connTo) || (c[0] === connTo && c[1] === connFrom))) return
    const next = [...connections, [connFrom, connTo]]; setConnections(next); setConnFrom(''); setConnTo('')
    scheduleSave(components, next, decisions)
  }
  const removeConnection = (i) => {
    const next = connections.filter((_, idx) => idx !== i); setConnections(next); scheduleSave(components, next, decisions)
  }
  const setDecision = (promptId, type, optId) => {
    const cur = new Set(decisions[promptId]?.selected || [])
    if (type === 'single') { cur.clear(); cur.add(optId) }
    else { cur.has(optId) ? cur.delete(optId) : cur.add(optId) }
    const next = { ...decisions, [promptId]: { selected: [...cur] } }
    setDecisions(next); scheduleSave(components, connections, next)
  }

  const doSubmit = async () => {
    setSubmitting(true)
    try {
      clearTimeout(saveTimer.current)
      await persist({ components, connections, decisions })
      await api.sysdesignSubmit(token, id)
      navigate(`/app/sysdesign/result/${id}`, { replace: true })
    } catch (err) { setError(err.message); setSubmitting(false); setConfirm(false) }
  }

  if (loading) return <div className="mx-auto max-w-5xl"><Card className="p-6"><LoadingBlock rows={8} /></Card></div>
  if (error) return <div className="mx-auto max-w-5xl"><Card className="p-6"><ErrorState message={error} onRetry={load} /></Card></div>
  if (!brief) return null
  const meta = difficultyMeta(attempt.difficulty)
  const addable = palette.filter((c) => !components.includes(c.id))

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link to="/app/sysdesign" className="flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200">
          <ArrowLeft size={15} /> Academy
        </Link>
        <div className="flex items-center gap-2">
          <span className="chip" style={{ background: `${meta.hex}22`, color: meta.hex }}>{meta.label}</span>
          <span className="text-xs text-slate-500">{saving === 'saving' ? 'Saving…' : saving === 'saved' ? 'Saved' : ''}</span>
        </div>
      </div>

      <Card glow className="p-5">
        <h1 className="text-lg font-extrabold text-white">{brief.title}</h1>
        <p className="mt-2 text-sm leading-relaxed text-slate-300">{brief.prompt}</p>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        {/* components + connections */}
        <div className="space-y-5">
          <Card className="p-5">
            <SectionHeading icon={Plus} title="Components" action={<Badge tone="muted">{components.length}</Badge>} />
            <div className="mt-3 flex flex-wrap gap-2">
              {components.length === 0 ? <p className="text-xs text-slate-500">Add components from the palette below.</p> : null}
              {components.map((cid) => {
                const Icon = componentIcon(cid)
                return (
                  <span key={cid} className="flex items-center gap-1.5 rounded-lg border border-brand-purple/30 bg-brand-soft px-2.5 py-1.5 text-xs text-white">
                    <Icon size={13} /> {paletteById[cid]?.label || cid}
                    <button onClick={() => removeComponent(cid)} className="ml-1 text-slate-400 hover:text-bad" aria-label="Remove"><X size={12} /></button>
                  </span>
                )
              })}
            </div>
            {addable.length ? (
              <>
                <p className="mt-4 mb-2 text-xs font-medium text-slate-400">Palette</p>
                <div className="flex flex-wrap gap-2">
                  {addable.map((c) => {
                    const Icon = componentIcon(c.id)
                    return (
                      <button key={c.id} onClick={() => addComponent(c.id)}
                        className="flex items-center gap-1.5 rounded-lg border border-white/5 bg-ink-900/60 px-2.5 py-1.5 text-xs text-slate-300 hover:border-white/10">
                        <Icon size={13} className="text-brand-violet" /> {c.label} <Plus size={11} />
                      </button>
                    )
                  })}
                </div>
              </>
            ) : null}
          </Card>

          <Card className="p-5">
            <SectionHeading icon={Link2} title="Connections" action={<Badge tone="muted">{connections.length}</Badge>} />
            <div className="mt-3 flex items-center gap-2">
              <select className="input !py-2 text-xs" value={connFrom} onChange={(e) => setConnFrom(e.target.value)} aria-label="From">
                <option value="">From…</option>
                {components.map((cid) => <option key={cid} value={cid}>{paletteById[cid]?.label || cid}</option>)}
              </select>
              <span className="text-slate-500">→</span>
              <select className="input !py-2 text-xs" value={connTo} onChange={(e) => setConnTo(e.target.value)} aria-label="To">
                <option value="">To…</option>
                {components.map((cid) => <option key={cid} value={cid}>{paletteById[cid]?.label || cid}</option>)}
              </select>
              <button className="btn-ghost !py-2" onClick={addConnection} disabled={!connFrom || !connTo || connFrom === connTo}><Plus size={14} /></button>
            </div>
            <div className="mt-3 space-y-1.5">
              {connections.map((c, i) => (
                <div key={i} className="flex items-center justify-between rounded-lg border border-white/5 bg-ink-900/60 px-3 py-2 text-xs text-slate-300">
                  <span>{paletteById[c[0]]?.label || c[0]} <span className="text-slate-500">→</span> {paletteById[c[1]]?.label || c[1]}</span>
                  <button onClick={() => removeConnection(i)} className="text-slate-500 hover:text-bad" aria-label="Remove"><Trash2 size={13} /></button>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* decision prompts */}
        <div className="space-y-5">
          <Card className="p-5">
            <SectionHeading icon={Check} title="Design decisions" />
            <div className="mt-4 space-y-5">
              {brief.decision_prompts.map((dp) => {
                const sel = new Set(decisions[dp.id]?.selected || [])
                return (
                  <div key={dp.id}>
                    <p className="text-sm font-semibold text-slate-200">{dp.prompt}</p>
                    {dp.type === 'multi' ? <p className="text-[11px] text-slate-500">Select all that apply</p> : null}
                    <div className="mt-2 space-y-1.5">
                      {dp.options.map((o) => {
                        const on = sel.has(o.id)
                        return (
                          <button key={o.id} onClick={() => setDecision(dp.id, dp.type, o.id)}
                            className={`flex w-full items-center gap-2.5 rounded-lg border p-2.5 text-left text-xs transition-all ${
                              on ? 'border-brand-purple/50 bg-brand-soft text-white' : 'border-white/5 bg-ink-900/60 text-slate-300 hover:border-white/10'
                            }`}>
                            <span className={`grid h-4 w-4 shrink-0 place-items-center border ${dp.type === 'multi' ? 'rounded' : 'rounded-full'} ${on ? 'border-brand-violet bg-brand-violet text-white' : 'border-white/20'}`}>
                              {on ? <Check size={10} /> : null}
                            </span>
                            {o.text}
                          </button>
                        )
                      })}
                    </div>
                  </div>
                )
              })}
            </div>
          </Card>
          <button className="btn-primary w-full !py-3" onClick={() => setConfirm(true)}>Submit design <Send size={15} /></button>
        </div>
      </div>

      {confirm ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4" onClick={() => !submitting && setConfirm(false)}>
          <Card className="w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-sm font-bold text-white">Submit your design?</h3>
            <p className="mt-1 text-sm text-slate-400">
              {components.length} components, {connections.length} connections, {Object.keys(decisions).length} decisions. You cannot change it after submitting.
            </p>
            <div className="mt-5 flex justify-end gap-3">
              <button className="btn-ghost" onClick={() => setConfirm(false)} disabled={submitting}>Keep editing</button>
              <button className="btn-primary" onClick={doSubmit} disabled={submitting}>
                {submitting ? <Spinner label="Submitting…" /> : (<>Submit <Send size={15} /></>)}
              </button>
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  )
}
