import { CalendarDays } from 'lucide-react'
import { Card, EmptyState, ErrorState, LoadingBlock, SectionHeading } from './ui.jsx'

// Renders ~12 weeks of real activity as a GitHub-style heatmap. Uses only backend-provided per-day
// counts (real timestamps); pre-activation / no-activity days are honest blanks, never fabricated.
const WEEKS = 12

function buildGrid(events) {
  const counts = new Map((events || []).map((e) => [e.date, e.count]))
  const today = new Date()
  const days = []
  const total = WEEKS * 7
  for (let i = total - 1; i >= 0; i--) {
    const d = new Date(today)
    d.setDate(today.getDate() - i)
    const iso = d.toISOString().slice(0, 10)
    days.push({ iso, count: counts.get(iso) || 0 })
  }
  // chunk into columns of 7 (weeks)
  const weeks = []
  for (let i = 0; i < days.length; i += 7) weeks.push(days.slice(i, i + 7))
  return weeks
}

function cellColor(count) {
  if (count <= 0) return 'rgba(255,255,255,0.05)'
  if (count === 1) return 'rgba(139,92,246,0.45)'
  if (count === 2) return 'rgba(139,92,246,0.7)'
  return '#8b5cf6'
}

export function ActivityHeatmap({ data, loading, error, retry }) {
  const events = data?.events || []
  const weeks = buildGrid(events)
  const hasAny = events.some((e) => e.count > 0)

  return (
    <Card className="p-5">
      <SectionHeading icon={CalendarDays} title="Activity" />
      <div className="mt-4">
        {loading ? (
          <LoadingBlock rows={3} />
        ) : error ? (
          <ErrorState message={error.message} onRetry={retry} />
        ) : !hasAny ? (
          <EmptyState
            title="No activity yet"
            hint="Your practice activity will appear here from now on. (We don’t backfill past dates.)"
          />
        ) : (
          <div className="overflow-x-auto">
            <div className="flex gap-1">
              {weeks.map((week, wi) => (
                <div key={wi} className="flex flex-col gap-1">
                  {week.map((day) => (
                    <span
                      key={day.iso}
                      title={`${day.iso}: ${day.count} activity`}
                      className="h-3 w-3 rounded-[3px]"
                      style={{ background: cellColor(day.count) }}
                    />
                  ))}
                </div>
              ))}
            </div>
            <p className="mt-3 text-[11px] text-slate-500">Last {WEEKS} weeks · real activity only</p>
          </div>
        )}
      </div>
    </Card>
  )
}
