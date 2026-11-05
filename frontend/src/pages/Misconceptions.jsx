import { Link } from 'react-router-dom'
import { ArrowRight, BookOpen, CheckCircle2, Target } from 'lucide-react'
import { motion } from 'framer-motion'
import { Badge, Card, EmptyState, ErrorState, LoadingBlock } from '../components/ui.jsx'
import { api } from '../api/client.js'
import { useApi } from '../lib/useApi.js'
import { frequencyLabel, misconceptionInfo, topicLabel } from '../lib/content.js'

export default function Misconceptions() {
  const { data, loading, error, retry } = useApi((t, id) => api.misconceptions(t, id))
  const items = data || []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-white">Misconceptions</h1>
        <p className="mt-1 text-sm text-slate-400">
          These are clear, recurring mistakes we detected in your answers. Missing or incomplete
          answers are never listed here — only genuine misunderstandings.
        </p>
      </div>

      {loading ? (
        <Card className="p-6"><LoadingBlock rows={5} /></Card>
      ) : error ? (
        <Card className="p-6"><ErrorState message={error.message} onRetry={retry} /></Card>
      ) : items.length === 0 ? (
        <Card className="p-6">
          <EmptyState
            icon={CheckCircle2}
            title="No misconceptions detected"
            hint="Nothing to fix right now. Keep practising — if a clear, repeated mistake appears, it will show up here with a plain-language explanation."
            action={<Link to="/app/practice" className="btn-primary"><Target size={15} /> Keep practising</Link>}
          />
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {items.map((m, i) => {
            const info = misconceptionInfo(m.tag)
            const freq = frequencyLabel(m.count)
            return (
              <motion.div
                key={m.tag}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
              >
                <Card className="flex h-full flex-col p-5">
                  <div className="flex items-start justify-between gap-3">
                    <h3 className="text-sm font-bold text-white">{info.title}</h3>
                    <Badge tone={freq.tone}>{freq.label}</Badge>
                  </div>
                  <p className="mt-2 flex-1 text-sm leading-relaxed text-slate-400">{info.explain}</p>
                  <div className="mt-4 flex items-center justify-between">
                    <span className="text-xs text-slate-500">
                      Seen {m.count} time{m.count > 1 ? 's' : ''}
                    </span>
                    {info.topic ? (
                      <Link
                        to="/app/practice"
                        state={{ topic: info.topic, context: { type: 'misconception', title: info.title, explain: info.explain } }}
                        className="flex items-center gap-1 text-xs font-medium text-brand-violet hover:underline"
                      >
                        <BookOpen size={13} /> Practise {topicLabel(info.topic)} <ArrowRight size={13} />
                      </Link>
                    ) : (
                      <Link to="/app/practice" className="flex items-center gap-1 text-xs font-medium text-brand-violet hover:underline">
                        Practise this <ArrowRight size={13} />
                      </Link>
                    )}
                  </div>
                </Card>
              </motion.div>
            )
          })}
        </div>
      )}
    </div>
  )
}
