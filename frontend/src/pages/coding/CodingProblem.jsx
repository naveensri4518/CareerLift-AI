import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  ArrowLeft,
  CheckCircle2,
  Clock,
  Code2,
  History,
  Info,
  Play,
  Send,
  ShieldAlert,
  XCircle,
} from 'lucide-react'
import { motion } from 'framer-motion'
import { Badge, Card, ErrorState, LoadingBlock, SectionHeading, Spinner } from '../../components/ui.jsx'
import { api } from '../../api/client.js'
import { useApi } from '../../lib/useApi.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { difficultyMeta, languageLabel, STARTER, verdictMeta } from '../../lib/coding.js'

const LANG_KEY = (id) => `careerlift.coding.${id}` // per-problem draft persistence (client-side only)

function VerdictPill({ verdict }) {
  const m = verdictMeta(verdict)
  return (
    <span className="chip" style={{ background: `${m.hex}22`, color: m.hex }}>
      {m.ok ? <CheckCircle2 size={13} /> : <XCircle size={13} />} {m.label}
    </span>
  )
}

function TestResultRow({ r }) {
  const m = verdictMeta(r.verdict)
  return (
    <div className="rounded-xl border border-white/5 bg-ink-900/60 p-3.5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-semibold text-slate-200">Sample test #{r.index}</span>
        <span className="flex items-center gap-2 text-xs">
          <span style={{ color: m.hex }}>{m.label}</span>
          <span className="text-slate-500">· {r.time_ms} ms</span>
        </span>
      </div>
      {!r.passed ? (
        <div className="mt-3 grid gap-2 text-xs sm:grid-cols-3">
          <div>
            <p className="mb-1 text-slate-500">Input</p>
            <pre className="overflow-x-auto rounded-lg bg-ink-950/70 p-2 text-slate-300">{r.input}</pre>
          </div>
          <div>
            <p className="mb-1 text-slate-500">Expected</p>
            <pre className="overflow-x-auto rounded-lg bg-ink-950/70 p-2 text-good">{r.expected}</pre>
          </div>
          <div>
            <p className="mb-1 text-slate-500">Your output</p>
            <pre className="overflow-x-auto rounded-lg bg-ink-950/70 p-2 text-bad">{r.actual || '(empty)'}</pre>
          </div>
        </div>
      ) : null}
      {r.stderr ? (
        <pre className="mt-2 overflow-x-auto rounded-lg border border-bad/20 bg-bad/5 p-2 text-xs text-bad">{r.stderr}</pre>
      ) : null}
    </div>
  )
}

function ResultPanel({ result, running }) {
  if (running) {
    return <Card className="p-5"><Spinner label="Executing in the secure sandbox…" /></Card>
  }
  if (!result) {
    return (
      <Card className="p-5">
        <SectionHeading icon={Info} title="Results" />
        <p className="mt-3 text-sm text-slate-500">
          Run the sample tests or submit for full grading. Hidden tests are evaluated on submit and never
          shown.
        </p>
      </Card>
    )
  }
  const m = verdictMeta(result.verdict)
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
      <Card className="p-5">
        <div className="flex items-center justify-between gap-3">
          <SectionHeading icon={m.ok ? CheckCircle2 : XCircle} title={result.mode === 'run' ? 'Sample run' : 'Submission result'} />
          <VerdictPill verdict={result.verdict} />
        </div>

        {result.verdict === 'COMPILATION ERROR' ? (
          <pre className="mt-4 overflow-x-auto rounded-lg border border-warn/20 bg-warn/5 p-3 text-xs text-warn">
            {result.compile_error}
          </pre>
        ) : (
          <>
            <div className="mt-4 flex flex-wrap gap-4 text-sm">
              <span className="flex items-center gap-1.5 text-slate-300">
                <CheckCircle2 size={14} className="text-good" />
                {result.tests_passed}/{result.tests_total} tests passed
              </span>
              <span className="flex items-center gap-1.5 text-slate-400">
                <Clock size={14} /> max {result.max_time_ms} ms
              </span>
              {result.mode !== 'run' && result.hidden_tests_total ? (
                <span className="text-slate-500">({result.hidden_tests_total} hidden)</span>
              ) : null}
            </div>
            {result.public_results?.length ? (
              <div className="mt-4 space-y-2.5">
                {result.public_results.map((r) => (
                  <TestResultRow key={r.index} r={r} />
                ))}
              </div>
            ) : null}
          </>
        )}
      </Card>
    </motion.div>
  )
}

function SubmissionHistory({ problemId, refreshKey }) {
  const { data, loading, error } = useApi((t) => api.codingSubmissions(t, problemId), [refreshKey])
  const subs = data?.submissions || []
  return (
    <Card className="p-5">
      <SectionHeading icon={History} title="Your submissions" action={subs.length ? <Badge tone="muted">{subs.length}</Badge> : null} />
      <div className="mt-4">
        {loading ? (
          <LoadingBlock rows={3} />
        ) : error ? (
          <ErrorState message={error.message} />
        ) : subs.length === 0 ? (
          <p className="text-sm text-slate-500">No submissions yet for this problem.</p>
        ) : (
          <div className="space-y-2">
            {subs.map((s) => (
              <div key={s.id} className="flex items-center justify-between gap-3 rounded-xl border border-white/5 bg-ink-900/50 px-3.5 py-2.5 text-sm">
                <span className="flex items-center gap-2">
                  <VerdictPill verdict={s.verdict} />
                  <span className="text-slate-500">{languageLabel(s.language)}</span>
                </span>
                <span className="text-xs text-slate-500">
                  {s.tests_passed}/{s.tests_total} · {new Date(s.created_at).toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  )
}

export default function CodingProblem() {
  const { id } = useParams()
  const { token } = useAuth()
  const { data: problem, loading, error, retry } = useApi((t) => api.codingProblem(t, id), [id])
  const { data: statusData } = useApi((t) => api.codingStatus(t))
  const sandboxOk = statusData?.sandbox_available

  const [language, setLanguage] = useState('python')
  const [source, setSource] = useState(STARTER.python)
  const [running, setRunning] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null)
  const [actionError, setActionError] = useState(null)
  const [historyKey, setHistoryKey] = useState(0)

  // Restore a saved draft (per problem+language) or fall back to the language starter.
  useEffect(() => {
    if (!id) return
    const saved = localStorage.getItem(`${LANG_KEY(id)}.${language}`)
    setSource(saved ?? STARTER[language])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, language])

  const onEditSource = (val) => {
    setSource(val)
    if (id) localStorage.setItem(`${LANG_KEY(id)}.${language}`, val)
  }

  const meta = useMemo(() => (problem ? difficultyMeta(problem.difficulty) : null), [problem])

  const act = async (kind) => {
    const isRun = kind === 'run'
    setResult(null)
    setActionError(null)
    isRun ? setRunning(true) : setSubmitting(true)
    try {
      const body = { problem_id: id, language, source }
      const res = isRun ? await api.codingRun(token, body) : await api.codingSubmit(token, body)
      setResult(res)
      if (!isRun) setHistoryKey((k) => k + 1)
    } catch (err) {
      setActionError(err.message)
    } finally {
      isRun ? setRunning(false) : setSubmitting(false)
    }
  }

  if (loading) return <div className="mx-auto max-w-6xl"><Card className="p-6"><LoadingBlock rows={8} /></Card></div>
  if (error) return <div className="mx-auto max-w-6xl"><Card className="p-6"><ErrorState message={error.message} onRetry={retry} /></Card></div>
  if (!problem) return null

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <Link to="/app/coding" className="flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200">
          <ArrowLeft size={15} /> Coding Arena
        </Link>
        <div className="flex items-center gap-2">
          <span className="chip" style={{ background: `${meta.hex}22`, color: meta.hex }}>{meta.label}</span>
          {problem.solved ? (
            <span className="flex items-center gap-1 text-xs font-semibold text-good"><CheckCircle2 size={14} /> Solved</span>
          ) : null}
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        {/* Left: problem statement */}
        <div className="space-y-5">
          <Card className="p-6">
            <h1 className="text-xl font-extrabold text-white">{problem.title}</h1>
            <p className="mt-3 text-sm leading-relaxed text-slate-300">{problem.description}</p>

            <div className="mt-5 space-y-4 text-sm">
              <div>
                <p className="mb-1 font-semibold text-slate-200">Input</p>
                <p className="text-slate-400">{problem.input_format}</p>
              </div>
              <div>
                <p className="mb-1 font-semibold text-slate-200">Output</p>
                <p className="text-slate-400">{problem.output_format}</p>
              </div>
              {problem.constraints?.length ? (
                <div>
                  <p className="mb-1 font-semibold text-slate-200">Constraints</p>
                  <ul className="list-inside list-disc text-slate-400">
                    {problem.constraints.map((c, i) => <li key={i}>{c}</li>)}
                  </ul>
                </div>
              ) : null}
              <div className="flex flex-wrap gap-4 text-xs text-slate-500">
                <span>Time limit: {problem.limits?.time_ms} ms</span>
                <span>Memory: {problem.limits?.memory_mb} MB</span>
                <span>{problem.public_test_count} sample · {problem.hidden_test_count} hidden tests</span>
              </div>
            </div>
          </Card>

          {problem.examples?.length ? (
            <Card className="p-6">
              <SectionHeading icon={Code2} title="Examples" />
              <div className="mt-4 space-y-3">
                {problem.examples.map((ex, i) => (
                  <div key={i} className="grid gap-2 sm:grid-cols-2">
                    <div>
                      <p className="mb-1 text-xs text-slate-500">Input</p>
                      <pre className="overflow-x-auto rounded-lg bg-ink-950/70 p-2.5 text-xs text-slate-300">{ex.input}</pre>
                    </div>
                    <div>
                      <p className="mb-1 text-xs text-slate-500">Output</p>
                      <pre className="overflow-x-auto rounded-lg bg-ink-950/70 p-2.5 text-xs text-slate-300">{ex.output}</pre>
                    </div>
                    {ex.explanation ? <p className="sm:col-span-2 text-xs text-slate-500">{ex.explanation}</p> : null}
                  </div>
                ))}
              </div>
            </Card>
          ) : null}

          <SubmissionHistory problemId={id} refreshKey={historyKey} />
        </div>

        {/* Right: editor + actions + results */}
        <div className="space-y-5">
          <Card className="p-5">
            <div className="flex items-center justify-between gap-3">
              <SectionHeading icon={Code2} title="Code editor" />
              <select
                className="input !w-auto !py-1.5 !px-2.5 text-xs"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                aria-label="Language"
              >
                <option value="python">Python 3</option>
                <option value="cpp">C++17</option>
                <option value="java">Java 17</option>
              </select>
            </div>
            <textarea
              className="input mt-4 min-h-[340px] resize-y font-mono text-[13px] leading-relaxed"
              spellCheck={false}
              value={source}
              maxLength={60000}
              onChange={(e) => onEditSource(e.target.value)}
            />
            {!sandboxOk && statusData ? (
              <p className="mt-3 flex items-start gap-1.5 text-xs text-warn">
                <ShieldAlert size={13} className="mt-0.5 shrink-0" />
                Sandbox unavailable — Run/Submit are disabled. {statusData.reason}
              </p>
            ) : null}
            {actionError ? <div className="mt-3"><ErrorState message={actionError} /></div> : null}
            <div className="mt-4 flex flex-wrap gap-3">
              <button
                className="btn-ghost !py-3"
                onClick={() => act('run')}
                disabled={running || submitting || sandboxOk === false}
              >
                {running ? <Spinner label="Running…" /> : (<><Play size={15} /> Run sample tests</>)}
              </button>
              <button
                className="btn-primary !py-3"
                onClick={() => act('submit')}
                disabled={running || submitting || sandboxOk === false}
              >
                {submitting ? <Spinner label="Submitting…" /> : (<><Send size={15} /> Submit</>)}
              </button>
            </div>
          </Card>

          <ResultPanel result={result} running={running || submitting} />
        </div>
      </div>
    </div>
  )
}
