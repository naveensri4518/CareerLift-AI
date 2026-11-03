import { motion } from 'framer-motion'
import { AlertTriangle, CheckCircle2, Inbox, Loader2, RefreshCw } from 'lucide-react'
import { bandMeta } from '../lib/content.js'

export function Card({ className = '', glow = false, children, as: Tag = 'div', ...rest }) {
  return (
    <Tag className={`${glow ? 'card-glow' : 'card'} ${className}`} {...rest}>
      {children}
    </Tag>
  )
}

export function SectionHeading({ icon: Icon, title, action }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="flex items-center gap-2.5">
        {Icon ? (
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-soft text-brand-violet">
            <Icon size={16} />
          </span>
        ) : null}
        <h3 className="section-title">{title}</h3>
      </div>
      {action}
    </div>
  )
}

export function Spinner({ label = 'Loading…', className = '' }) {
  return (
    <div className={`flex items-center gap-2 text-sm text-slate-400 ${className}`} role="status" aria-live="polite">
      <Loader2 size={16} className="animate-spin" />
      <span>{label}</span>
    </div>
  )
}

export function LoadingBlock({ label = 'Loading…', rows = 3 }) {
  return (
    <div className="space-y-3" role="status" aria-live="polite" aria-label={label}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-4 w-full animate-pulse rounded bg-white/5" />
      ))}
      <span className="sr-only">{label}</span>
    </div>
  )
}

export function EmptyState({ icon: Icon = Inbox, title, hint, action }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-white/10 bg-white/[0.02] px-6 py-10 text-center">
      <span className="grid h-11 w-11 place-items-center rounded-full bg-white/5 text-slate-400">
        <Icon size={20} />
      </span>
      <div>
        <p className="text-sm font-semibold text-slate-200">{title}</p>
        {hint ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null}
      </div>
      {action}
    </div>
  )
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="flex flex-col items-start gap-3 rounded-xl border border-bad/20 bg-bad/5 px-4 py-4" role="alert">
      <div className="flex items-center gap-2 text-sm font-medium text-bad">
        <AlertTriangle size={16} />
        <span>{message || 'Something went wrong.'}</span>
      </div>
      {onRetry ? (
        <button className="btn-ghost" onClick={onRetry}>
          <RefreshCw size={14} /> Try again
        </button>
      ) : null}
    </div>
  )
}

export function Toast({ kind = 'success', children }) {
  const good = kind === 'success'
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex items-center gap-2 rounded-xl px-4 py-3 text-sm ${
        good ? 'bg-good/10 text-good border border-good/20' : 'bg-bad/10 text-bad border border-bad/20'
      }`}
      role="status"
    >
      {good ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
      <span>{children}</span>
    </motion.div>
  )
}

const toneClasses = {
  good: 'bg-good/15 text-good',
  warn: 'bg-warn/15 text-warn',
  bad: 'bg-bad/15 text-bad',
  muted: 'bg-white/10 text-slate-300',
}

export function Badge({ tone = 'muted', children }) {
  return <span className={`chip ${toneClasses[tone] || toneClasses.muted}`}>{children}</span>
}

// Accent styling for premium metric tiles. Keys map to the tailwind `accent` palette.
const accentStyles = {
  purple: { icon: 'bg-accent-purple/15 text-accent-purple', glow: 'rgba(139,92,246,0.18)' },
  blue: { icon: 'bg-accent-blue/15 text-accent-blue', glow: 'rgba(59,130,246,0.18)' },
  green: { icon: 'bg-accent-green/15 text-accent-green', glow: 'rgba(34,197,94,0.18)' },
  orange: { icon: 'bg-accent-orange/15 text-accent-orange', glow: 'rgba(249,115,22,0.18)' },
}

// A premium metric tile. `value` MUST be real data from the backend (no fabricated numbers).
// `loading` renders a skeleton; `value` of null/undefined renders an honest dash.
export function StatCard({ icon: Icon, label, value, hint, accent = 'purple', delay = 0, loading = false }) {
  const style = accentStyles[accent] || accentStyles.purple
  const display = value === null || value === undefined ? '—' : value
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay, ease: 'easeOut' }}
      className="stat-card"
    >
      <div
        className="pointer-events-none absolute -right-6 -top-8 h-24 w-24 rounded-full blur-2xl"
        style={{ background: style.glow }}
      />
      <div className="relative flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
          {loading ? (
            <div className="mt-2 h-7 w-16 animate-pulse rounded bg-white/10" />
          ) : (
            <p className="mt-1 text-2xl font-extrabold text-white">{display}</p>
          )}
          {hint ? <p className="mt-1 truncate text-[11px] text-slate-500">{hint}</p> : null}
        </div>
        {Icon ? (
          <span className={`stat-icon ${style.icon}`}>
            <Icon size={18} />
          </span>
        ) : null}
      </div>
    </motion.div>
  )
}

// A labelled band bar (e.g. a concept's latest result). Shows the BAND, not a fake percentage.
export function BandBar({ label, band, sublabel }) {
  const meta = bandMeta(band)
  return (
    <div className="flex items-center gap-3">
      <span className="w-40 shrink-0 truncate text-sm text-slate-300">{label}</span>
      <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-white/5">
        <motion.div
          className="h-full rounded-full"
          style={{ background: meta.hex }}
          initial={{ width: 0 }}
          animate={{ width: `${meta.pct}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
        />
      </div>
      <span className="w-20 shrink-0 text-right text-xs font-semibold" style={{ color: meta.hex }}>
        {sublabel || meta.label}
      </span>
    </div>
  )
}

// Circular gauge for a single band. No numeric score is invented — it shows the band name.
export function BandGauge({ band, caption = 'Overall' }) {
  const meta = bandMeta(band)
  const r = 54
  const circ = 2 * Math.PI * r
  const dash = (meta.pct / 100) * circ
  return (
    <div className="relative grid place-items-center">
      <svg width="140" height="140" viewBox="0 0 140 140" className="-rotate-90">
        <circle cx="70" cy="70" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="12" />
        <motion.circle
          cx="70"
          cy="70"
          r={r}
          fill="none"
          stroke={meta.hex}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circ}`}
          initial={{ strokeDasharray: `0 ${circ}` }}
          animate={{ strokeDasharray: `${dash} ${circ}` }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-xl font-extrabold" style={{ color: meta.hex }}>
          {meta.label}
        </span>
        <span className="text-[11px] uppercase tracking-wide text-slate-500">{caption}</span>
      </div>
    </div>
  )
}
