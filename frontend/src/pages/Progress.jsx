import { Link } from 'react-router-dom'
import { BarChart3, Code2, History, MessageSquare, Mic, TrendingUp } from 'lucide-react'
import {
  Badge,
  BandBar,
  Card,
  EmptyState,
  ErrorState,
  LoadingBlock,
  SectionHeading,
} from '../components/ui.jsx'
import { ProgressChart } from '../components/ProgressChart.jsx'
import { api } from '../api/client.js'
import { useApi } from '../lib/useApi.js'
import { bandMeta, topicLabel } from '../lib/content.js'

function HistoryRow({ item, index }) {
  const tech = item.abstained_technical ? null : item.technical_band
  const comm = item.abstained_communication ? null : item.communication_band
  const date = item.created_at ? new Date(item.created_at).toLocaleString() : ''
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-white/5 bg-ink-900/50 p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-slate-500">#{index + 1}</span>
          <span className="truncate text-sm font-medium text-slate-200">{topicLabel(item.topic)}</span>
        </div>
        <p className="mt-0.5 text-xs text-slate-500">{date}</p>
      </div>
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5 text-xs">
          <Code2 size={13} className="text-brand-violet" />
          <span className="font-semibold" style={{ color: bandMeta(tech).hex }}>{tech || '—'}</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs">
          <MessageSquare size={13} className="text-brand-blue" />
          <span className="font-semibold" style={{ color: bandMeta(comm).hex }}>{comm || '—'}</span>
        </div>
      </div>
    </div>
  )
}

export default function Progress() {
  const { data, loading, error, retry } = useApi((t, id) => api.history(t, id))
  const history = data || []

  const byTopic = new Map()
  for (const h of history) {
    if (!h.abstained_technical && h.technical_band) byTopic.set(h.topic, h.technical_band)
  }
  const conceptRows = [...byTopic.entries()]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-white">My Progress</h1>
        <p className="mt-1 text-sm text-slate-400">
          Your real interview history and how your two scores have moved over time.
        </p>
      </div>

      {loading ? (
        <Card className="p-6"><LoadingBlock rows={6} /></Card>
      ) : error ? (
        <Card className="p-6"><ErrorState message={error.message} onRetry={retry} /></Card>
      ) : history.length === 0 ? (
        <Card className="p-6">
          <EmptyState
            icon={History}
            title="No interviews yet"
            hint="Your scores, trends, and concept progress appear here once you’ve practised."
            action={<Link to="/app/practice" className="btn-primary"><Mic size={15} /> Start practising</Link>}
          />
        </Card>
      ) : (
        <>
          <div className="grid gap-5 lg:grid-cols-2">
            <Card className="p-5">
              <SectionHeading icon={TrendingUp} title="Score trends (Technical & Communication)" />
              <div className="mt-4"><ProgressChart history={history} /></div>
            </Card>
            <Card className="p-5">
              <SectionHeading icon={BarChart3} title="Latest result by concept" />
              <div className="mt-4">
                {conceptRows.length === 0 ? (
                  <EmptyState title="No scored concepts yet" hint="Finish a scored interview to populate this." />
                ) : (
                  <div className="space-y-3.5">
                    {conceptRows.map(([topic, band]) => (
                      <BandBar key={topic} label={topicLabel(topic)} band={band} />
                    ))}
                  </div>
                )}
              </div>
            </Card>
          </div>

          <Card className="p-5">
            <SectionHeading
              icon={History}
              title="Interview history"
              action={<Badge tone="muted">{history.length} total</Badge>}
            />
            <div className="mt-4 space-y-2.5">
              {[...history].reverse().map((item, i) => (
                <HistoryRow key={item.id ?? i} item={item} index={history.length - 1 - i} />
              ))}
            </div>
          </Card>
        </>
      )}
    </div>
  )
}
