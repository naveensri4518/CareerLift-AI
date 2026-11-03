import { motion } from 'framer-motion'
import { Target } from 'lucide-react'
import { Card, EmptyState, ErrorState, LoadingBlock, SectionHeading, Badge } from './ui.jsx'
import { masteryMeta } from '../lib/mastery.js'
import { topicLabel } from '../lib/content.js'

// Maps a concept id to a friendly title without exposing raw ids. Falls back to a prettified form.
function conceptTitle(conceptId) {
  // The frontend intentionally does not ship the full concept reference; show a readable label.
  const pretty = conceptId.replace(/^C-/, '').replace(/-/g, ' ').toLowerCase()
  return pretty.charAt(0).toUpperCase() + pretty.slice(1)
}

export function MasteryPanel({ data, loading, error, retry }) {
  const concepts = data?.concepts || []
  return (
    <Card className="p-5">
      <SectionHeading
        icon={Target}
        title="Concept mastery"
        action={data?.summary ? <Badge tone="muted">{data.summary.tracked} tracked</Badge> : null}
      />
      <div className="mt-4">
        {loading ? (
          <LoadingBlock rows={4} />
        ) : error ? (
          <ErrorState message={error.message} onRetry={retry} />
        ) : concepts.length === 0 ? (
          <EmptyState
            title="No tracked concepts yet"
            hint="As you practise, each concept earns a mastery label here — honestly, from your real answers (not a made-up score)."
          />
        ) : (
          <div className="space-y-3.5">
            {concepts.map((c) => {
              const meta = masteryMeta(c.label)
              return (
                <div key={c.concept_id}>
                  <div className="mb-1 flex items-center justify-between gap-2 text-sm">
                    <span className="truncate text-slate-300">{conceptTitle(c.concept_id)}</span>
                    <span className="flex items-center gap-2">
                      {c.open_misconception ? <Badge tone="bad">misconception</Badge> : null}
                      <span className="text-xs font-semibold" style={{ color: meta.hex }}>
                        {c.label}
                      </span>
                    </span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-white/5">
                    <motion.div
                      className="h-full rounded-full"
                      style={{ background: meta.hex }}
                      initial={{ width: 0 }}
                      animate={{ width: `${meta.pct}%` }}
                      transition={{ duration: 0.5 }}
                    />
                  </div>
                  {c.label === 'Not enough evidence' ? (
                    <p className="mt-1 text-[11px] text-slate-500">
                      {c.independent_success_count}/3 independent successes needed to assess
                    </p>
                  ) : null}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </Card>
  )
}
