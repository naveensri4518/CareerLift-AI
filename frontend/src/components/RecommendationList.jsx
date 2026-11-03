import { Link } from 'react-router-dom'
import { ArrowRight, Lightbulb, Sparkles } from 'lucide-react'
import { Card, EmptyState, ErrorState, LoadingBlock, SectionHeading } from './ui.jsx'
import { actionLabel } from '../lib/mastery.js'
import { topicLabel } from '../lib/content.js'

const PRIORITY_TONE = {
  misconception: 'text-bad border-bad/30 bg-bad/5',
  prerequisite: 'text-warn border-warn/30 bg-warn/5',
  spaced_due: 'text-brand-violet border-brand-purple/30 bg-brand-soft',
}

export function RecommendationList({ data, loading, error, retry }) {
  return (
    <Card className="p-5">
      <SectionHeading icon={Sparkles} title="Recommended for you" />
      <div className="mt-4">
        {loading ? (
          <LoadingBlock rows={3} />
        ) : error ? (
          <ErrorState message={error.message} onRetry={retry} />
        ) : !data?.length ? (
          <EmptyState
            title="No recommendations yet"
            hint="Finish a practice interview and we’ll suggest exactly what to work on next."
            action={
              <Link to="/app/practice" className="btn-primary">
                Start practising <ArrowRight size={15} />
              </Link>
            }
          />
        ) : (
          <div className="space-y-3">
            {data.slice(0, 5).map((r, i) => (
              <div
                key={`${r.concept_id}-${i}`}
                className={`rounded-xl border p-3.5 ${PRIORITY_TONE[r.priority] || 'border-white/10 bg-white/[0.03]'}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold uppercase tracking-wide">
                    {actionLabel(r.action)}
                    {r.target_ref ? ` · ${topicLabel(r.target_ref)}` : ''}
                  </span>
                  <Link
                    to="/app/practice"
                    className="flex items-center gap-1 text-xs font-medium text-slate-200 hover:underline"
                  >
                    Go <ArrowRight size={13} />
                  </Link>
                </div>
                <p className="mt-1.5 flex items-start gap-2 text-sm text-slate-200">
                  <Lightbulb size={15} className="mt-0.5 shrink-0 opacity-80" />
                  {r.reason}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  )
}
