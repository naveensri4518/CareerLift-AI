import { Link } from 'react-router-dom'
import {
  ArrowRight,
  Code2,
  Lightbulb,
  MessageSquare,
  RotateCcw,
  Sparkles,
  ThumbsUp,
  TriangleAlert,
} from 'lucide-react'
import { Badge, BandGauge, Card, SectionHeading } from '../../components/ui.jsx'
import { bandMeta } from '../../lib/content.js'
import { categoryLabel } from '../../lib/studio.js'

function AxisCard({ icon: Icon, tint, title, band }) {
  const meta = bandMeta(band)
  return (
    <Card className="p-5">
      <div className="flex items-center gap-2">
        <span className="grid h-8 w-8 place-items-center rounded-lg" style={{ background: `${tint}22`, color: tint }}>
          <Icon size={16} />
        </span>
        <span className="text-sm font-semibold text-slate-200">{title}</span>
        <span className="ml-auto text-lg font-extrabold" style={{ color: band ? meta.hex : '#64748b' }}>
          {band || 'Not assessed'}
        </span>
      </div>
      <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-white/5">
        <div className="h-full rounded-full" style={{ width: `${band ? meta.pct : 0}%`, background: meta.hex }} />
      </div>
    </Card>
  )
}

export function SessionResults({ session }) {
  const ev = session.evaluation || {}
  // overall = the weaker of the two present axes (honest, conservative; never an invented number)
  const present = [ev.overall_technical_band, ev.overall_communication_band].filter(Boolean)
  const overall =
    present.length === 0
      ? null
      : present.reduce((a, b) => (bandMeta(a).ordinal <= bandMeta(b).ordinal ? a : b))

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-white">Interview results</h1>
          <p className="mt-1 text-sm text-slate-400">
            {categoryLabel(session.category)} · {ev.questions_answered}/{ev.questions_total} answered
          </p>
        </div>
        <Link to="/app/interview" className="btn-ghost">
          <RotateCcw size={15} /> New interview
        </Link>
      </div>

      <div className="rounded-xl border border-brand-purple/30 bg-brand-soft px-4 py-2.5 text-xs font-medium text-brand-violet flex items-center gap-2">
        <Sparkles size={14} />
        Local demo evaluation — deterministic offline scoring, not a live AI model.
      </div>

      {/* Scores */}
      <div className="grid items-center gap-5 lg:grid-cols-[auto,1fr]">
        <Card className="grid place-items-center p-5">
          <BandGauge band={overall} caption="Overall" />
        </Card>
        <div className="grid gap-5 sm:grid-cols-2">
          <AxisCard icon={Code2} tint="#a78bfa" title="Technical correctness" band={ev.overall_technical_band} />
          <AxisCard icon={MessageSquare} tint="#3b82f6" title="Communication clarity" band={ev.overall_communication_band} />
        </div>
      </div>

      {/* Strengths + weaknesses */}
      <div className="grid gap-5 lg:grid-cols-2">
        <Card className="p-5">
          <SectionHeading icon={ThumbsUp} title="Strengths" />
          <div className="mt-3 space-y-2">
            {(ev.strengths || []).length ? (
              ev.strengths.map((s, i) => (
                <p key={i} className="flex items-start gap-2 text-sm text-slate-300">
                  <ThumbsUp size={14} className="mt-0.5 shrink-0 text-good" /> {s}
                </p>
              ))
            ) : (
              <p className="text-sm text-slate-500">Answer more questions to surface strengths.</p>
            )}
          </div>
        </Card>
        <Card className="p-5">
          <SectionHeading icon={TriangleAlert} title="Areas to improve" />
          <div className="mt-3 space-y-2">
            {(ev.weaknesses || []).length ? (
              ev.weaknesses.map((w, i) => (
                <p key={i} className="flex items-start gap-2 text-sm text-slate-300">
                  <TriangleAlert size={14} className="mt-0.5 shrink-0 text-warn" /> {w}
                </p>
              ))
            ) : (
              <p className="text-sm text-slate-500">No significant weaknesses detected in this session.</p>
            )}
          </div>
        </Card>
      </div>

      {/* Suggestions */}
      <Card className="p-5">
        <SectionHeading icon={Lightbulb} title="Suggested improvements" />
        <div className="mt-3 space-y-2">
          {(ev.suggestions || []).map((s, i) => (
            <p key={i} className="flex items-start gap-2 text-sm text-slate-300">
              <Lightbulb size={14} className="mt-0.5 shrink-0 text-brand-violet" /> {s}
            </p>
          ))}
        </div>
      </Card>

      {/* Sample better answer */}
      {ev.sample_better_answer?.text ? (
        <Card className="p-5">
          <SectionHeading icon={Code2} title={`A stronger answer — ${ev.sample_better_answer.topic}`} />
          <p className="mt-3 rounded-xl border border-white/5 bg-ink-900/60 p-3.5 text-sm leading-relaxed text-slate-300">
            {ev.sample_better_answer.text}
          </p>
        </Card>
      ) : null}

      {/* Recommended practice -> links back to Phase 0 surfaces */}
      {(ev.recommended_practice_topics || []).length || (ev.misconception_tags || []).length ? (
        <Card className="p-5">
          <SectionHeading icon={ArrowRight} title="Recommended next" />
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {(ev.recommended_practice_topics || []).map((t) => (
              <Badge key={t} tone="warn">{t}</Badge>
            ))}
            {(ev.misconception_tags || []).length ? (
              <Link to="/app/misconceptions" className="btn-ghost !py-2">
                Fix misconceptions <ArrowRight size={14} />
              </Link>
            ) : null}
            <Link to="/app/interview" className="btn-primary !py-2">
              Practise again <ArrowRight size={14} />
            </Link>
          </div>
          <p className="mt-3 text-xs text-slate-500">
            These results also feed your mastery and recommendations on the dashboard.
          </p>
        </Card>
      ) : null}
    </div>
  )
}
