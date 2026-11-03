import { Link } from 'react-router-dom'
import {
  ArrowRight,
  BookOpen,
  Brain,
  CalendarClock,
  ChevronRight,
  Clock,
  Code2,
  Flame,
  LineChart as LineChartIcon,
  ListChecks,
  MessageSquare,
  Mic,
  Target,
  TrendingUp,
} from 'lucide-react'
import { motion } from 'framer-motion'
import {
  Badge,
  BandBar,
  BandGauge,
  Card,
  EmptyState,
  ErrorState,
  LoadingBlock,
  SectionHeading,
  StatCard,
} from '../components/ui.jsx'
import { api } from '../api/client.js'
import { useApi } from '../lib/useApi.js'
import { useAuth } from '../context/AuthContext.jsx'
import { bandMeta, frequencyLabel, misconceptionInfo, topicLabel } from '../lib/content.js'
import { ProgressChart } from '../components/ProgressChart.jsx'
import { RecommendationList } from '../components/RecommendationList.jsx'
import { MasteryPanel } from '../components/MasteryPanel.jsx'
import { ActivityHeatmap } from '../components/ActivityHeatmap.jsx'

const QUICK = [
  { to: '/app/practice', title: 'Start Practice Interview', sub: 'Role-based, fair feedback', icon: Mic, primary: true },
  { to: '/app/progress', title: 'View My Progress', sub: 'Track your scores and growth', icon: BookOpen },
  { to: '/app/misconceptions', title: 'Fix Misconceptions', sub: 'See and resolve concept gaps', icon: Target },
  { to: '/app/planner', title: 'My Learning Planner', sub: 'Personalized study roadmap', icon: CalendarClock },
]

function QuickAction({ item }) {
  return (
    <Link
      to={item.to}
      className={`group flex items-center gap-3 rounded-2xl border p-4 transition-all ${
        item.primary
          ? 'border-brand-purple/40 bg-brand-gradient text-white shadow-[0_10px_30px_-12px_rgba(99,102,241,0.9)] hover:brightness-110'
          : 'border-white/5 bg-ink-850/80 text-slate-200 hover:border-white/10 hover:bg-ink-800'
      }`}
    >
      <span
        className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${
          item.primary ? 'bg-white/15' : 'bg-brand-soft text-brand-violet'
        }`}
      >
        <item.icon size={18} />
      </span>
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold">{item.title}</p>
        <p className={`truncate text-xs ${item.primary ? 'text-white/80' : 'text-slate-500'}`}>{item.sub}</p>
      </div>
      <ArrowRight
        size={16}
        className={`ml-auto shrink-0 transition-transform group-hover:translate-x-0.5 ${
          item.primary ? 'text-white/90' : 'text-slate-500'
        }`}
      />
    </Link>
  )
}

// Premium metric row. Every value comes from the REAL /overview endpoint — nothing is fabricated.
// Phase-2 "Problems Solved" is intentionally omitted (that feature is not built yet).
function StatsRow({ overview, loading }) {
  const o = overview || {}
  const skills = o.skills || {}
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard
        icon={Mic}
        label="Interviews Completed"
        value={o.interviews_completed}
        hint="Practice interviews you’ve taken"
        accent="purple"
        delay={0}
        loading={loading}
      />
      <StatCard
        icon={Brain}
        label="Concepts Tracked"
        value={skills.tracked}
        hint="Skills we’re following for you"
        accent="blue"
        delay={0.05}
        loading={loading}
      />
      <StatCard
        icon={Target}
        label="Open Misconceptions"
        value={skills.open_misconceptions}
        hint="Gaps to resolve"
        accent="orange"
        delay={0.1}
        loading={loading}
      />
      <StatCard
        icon={Flame}
        label="Day Streak"
        value={o.streak_days}
        hint="Consecutive active days"
        accent="green"
        delay={0.15}
        loading={loading}
      />
    </div>
  )
}

function timeAgo(iso) {
  if (!iso) return ''
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const mins = Math.max(0, Math.round((Date.now() - then) / 60000))
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} min ago`
  const hrs = Math.round(mins / 60)
  if (hrs < 24) return `${hrs} hour${hrs > 1 ? 's' : ''} ago`
  const days = Math.round(hrs / 24)
  return `${days} day${days > 1 ? 's' : ''} ago`
}

function LatestResult({ history }) {
  const scored = history.filter((h) => !h.abstained_technical || !h.abstained_communication)
  const latest = scored[scored.length - 1] || history[history.length - 1]

  if (!latest) {
    return (
      <Card className="p-5">
        <SectionHeading icon={Clock} title="Latest Interview Result" />
        <div className="mt-4">
          <EmptyState
            title="No interviews yet"
            hint="Finish your first practice interview to see your Technical and Communication results here."
            action={
              <Link to="/app/practice" className="btn-primary">
                <Mic size={15} /> Start now
              </Link>
            }
          />
        </div>
      </Card>
    )
  }

  const tech = latest.abstained_technical ? null : latest.technical_band
  const comm = latest.abstained_communication ? null : latest.communication_band
  // "Overall" gauge shows the WEAKER of the two bands as an honest, conservative summary (never a made-up number).
  const bandsPresent = [tech, comm].filter(Boolean)
  const overall =
    bandsPresent.length === 0
      ? null
      : bandsPresent.reduce((a, b) => (bandMeta(a).ordinal <= bandMeta(b).ordinal ? a : b))

  return (
    <Card className="p-5">
      <SectionHeading
        icon={Clock}
        title="Latest Interview Result"
        action={
          <Link to="/app/progress" className="flex items-center gap-1 text-xs text-brand-violet hover:underline">
            View details <ChevronRight size={14} />
          </Link>
        }
      />
      <p className="mt-1 text-xs text-slate-500">
        {topicLabel(latest.topic)} · {timeAgo(latest.created_at)}
      </p>

      <div className="mt-4 grid items-center gap-5 sm:grid-cols-[auto,1fr]">
        <BandGauge band={overall} caption="Overall" />
        <div className="space-y-3">
          <div className="rounded-xl border border-white/5 bg-ink-900/70 p-3.5">
            <div className="mb-2 flex items-center gap-2 text-slate-300">
              <Code2 size={15} className="text-brand-violet" />
              <span className="text-sm font-semibold">Technical</span>
              <span className="ml-auto text-sm font-bold" style={{ color: bandMeta(tech).hex }}>
                {tech || 'Not assessed'}
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-white/5">
              <div className="h-full rounded-full" style={{ width: `${bandMeta(tech).pct}%`, background: bandMeta(tech).hex }} />
            </div>
          </div>
          <div className="rounded-xl border border-white/5 bg-ink-900/70 p-3.5">
            <div className="mb-2 flex items-center gap-2 text-slate-300">
              <MessageSquare size={15} className="text-brand-blue" />
              <span className="text-sm font-semibold">Communication</span>
              <span className="ml-auto text-sm font-bold" style={{ color: bandMeta(comm).hex }}>
                {comm || 'Not assessed'}
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-white/5">
              <div className="h-full rounded-full" style={{ width: `${bandMeta(comm).pct}%`, background: bandMeta(comm).hex }} />
            </div>
          </div>
        </div>
      </div>
    </Card>
  )
}

// Technical performance by concept, derived from REAL history: latest band per topic.
function PerformanceByConcept({ history }) {
  const byTopic = new Map()
  for (const h of history) {
    if (h.abstained_technical || !h.technical_band) continue
    byTopic.set(h.topic, h.technical_band) // later entries overwrite -> latest wins
  }
  const rows = [...byTopic.entries()]

  return (
    <Card className="p-5">
      <SectionHeading icon={LineChartIcon} title="Technical Performance by Concept" />
      <div className="mt-4">
        {rows.length === 0 ? (
          <EmptyState
            title="No scored topics yet"
            hint="Your latest technical result per topic will appear here after you practise."
          />
        ) : (
          <div className="space-y-3.5">
            {rows.map(([topic, band]) => (
              <BandBar key={topic} label={topicLabel(topic)} band={band} />
            ))}
          </div>
        )}
      </div>
    </Card>
  )
}

function DetectedMisconceptions({ data, loading, error, retry }) {
  return (
    <Card className="p-5">
      <SectionHeading
        icon={Target}
        title="Detected Misconceptions"
        action={data?.length ? <Badge tone="bad">{data.length}</Badge> : null}
      />
      <div className="mt-4">
        {loading ? (
          <LoadingBlock rows={3} />
        ) : error ? (
          <ErrorState message={error.message} onRetry={retry} />
        ) : !data?.length ? (
          <EmptyState
            title="None detected"
            hint="Specific misconceptions only appear when a clear, repeated mistake shows up — not from missing or short answers."
          />
        ) : (
          <div className="space-y-2.5">
            {data.slice(0, 3).map((m) => {
              const info = misconceptionInfo(m.tag)
              const freq = frequencyLabel(m.count)
              return (
                <div
                  key={m.tag}
                  className="flex items-center justify-between gap-3 rounded-xl border border-white/5 bg-ink-900/60 px-3.5 py-2.5"
                >
                  <span className="truncate text-sm text-slate-200">{info.title}</span>
                  <Badge tone={freq.tone}>{freq.label}</Badge>
                </div>
              )
            })}
            <Link to="/app/misconceptions" className="flex items-center gap-1 pt-1 text-xs text-brand-violet hover:underline">
              View all <ChevronRight size={14} />
            </Link>
          </div>
        )}
      </div>
    </Card>
  )
}

function LearningPlan({ data, loading, error, retry }) {
  return (
    <Card className="p-5">
      <SectionHeading icon={ListChecks} title="Your Learning Plan" />
      <div className="mt-4">
        {loading ? (
          <LoadingBlock rows={3} />
        ) : error ? (
          <ErrorState message={error.message} onRetry={retry} />
        ) : !data ? (
          <EmptyState title="No plan yet" hint="Practise a question to get your first recommendation." />
        ) : (
          <div className="space-y-3">
            <div className="rounded-xl border border-brand-purple/20 bg-brand-soft p-3.5">
              <p className="text-xs font-medium uppercase tracking-wide text-brand-violet">Recommended next</p>
              <p className="mt-1 text-sm font-semibold text-white">{topicLabel(data.topic)}</p>
              <p className="mt-1 text-xs text-slate-400">{data.reason}</p>
            </div>
            <Link to="/app/planner" className="btn-ghost w-full">
              Open Learning Planner <ArrowRight size={15} />
            </Link>
          </div>
        )}
      </div>
    </Card>
  )
}

function ProgressOverTime({ history }) {
  return (
    <Card className="p-5">
      <SectionHeading icon={TrendingUp} title="Progress Over Time" />
      <div className="mt-4">
        <ProgressChart history={history} />
      </div>
    </Card>
  )
}

export default function Dashboard() {
  const { session } = useAuth()
  const name = session?.display_name

  const historyReq = useApi((t, id) => api.history(t, id))
  const miscReq = useApi((t, id) => api.misconceptions(t, id))
  const nextReq = useApi((t, id) => api.next(t, id))
  // Phase 0 — Learning Intelligence
  const recReq = useApi((t, id) => api.recommendations(t, id))
  const skillsReq = useApi((t, id) => api.skills(t, id))
  const activityReq = useApi((t, id) => api.activity(t, id))
  const overviewReq = useApi((t, id) => api.overview(t, id))

  const history = historyReq.data || []

  return (
    <div className="space-y-6">
      {/* Welcome banner */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative overflow-hidden rounded-2xl border border-white/5 bg-gradient-to-br from-brand-purple/15 via-ink-850 to-ink-900 p-6 sm:p-7"
      >
        <div className="pointer-events-none absolute right-0 top-0 h-full w-1/2 bg-[radial-gradient(60%_80%_at_80%_20%,rgba(99,102,241,0.25),transparent)]" />
        <h1 className="relative text-2xl font-extrabold text-white sm:text-3xl">
          Welcome{ name ? <>, <span className="gradient-text">{name}</span></> : <> to <span className="gradient-text">CareerLift AI</span></> }
        </h1>
        <p className="relative mt-2 max-w-xl text-sm text-slate-400">
          Practice real interviews, get fair and explainable feedback, and build the skills to crack your
          dream job.
        </p>
      </motion.div>

      {/* Real metric row — honest values from /overview, no fabricated numbers */}
      <StatsRow overview={overviewReq.data} loading={overviewReq.loading} />

      {/* Quick actions */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {QUICK.map((item) => (
          <QuickAction key={item.to} item={item} />
        ))}
      </div>

      {/* Row 1: latest result + performance by concept */}
      <div className="grid gap-5 lg:grid-cols-2">
        {historyReq.loading ? (
          <Card className="p-5"><LoadingBlock rows={5} /></Card>
        ) : historyReq.error ? (
          <Card className="p-5"><ErrorState message={historyReq.error.message} onRetry={historyReq.retry} /></Card>
        ) : (
          <LatestResult history={history} />
        )}
        {historyReq.loading ? (
          <Card className="p-5"><LoadingBlock rows={5} /></Card>
        ) : (
          <PerformanceByConcept history={history} />
        )}
      </div>

      {/* Row 2: Learning Intelligence — recommendations (spans 2) + activity */}
      <div className="grid gap-5 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <RecommendationList
            data={recReq.data?.recommendations}
            loading={recReq.loading}
            error={recReq.error}
            retry={recReq.retry}
          />
        </div>
        <ActivityHeatmap
          data={activityReq.data}
          loading={activityReq.loading}
          error={activityReq.error}
          retry={activityReq.retry}
        />
      </div>

      {/* Row 3: concept mastery (full width) */}
      <MasteryPanel data={skillsReq.data} loading={skillsReq.loading} error={skillsReq.error} retry={skillsReq.retry} />

      {/* Row 4: misconceptions + plan + progress */}
      <div className="grid gap-5 lg:grid-cols-3">
        <DetectedMisconceptions {...miscReq} data={miscReq.data} />
        <LearningPlan {...nextReq} data={nextReq.data} />
        <ProgressOverTime history={history} />
      </div>
    </div>
  )
}
