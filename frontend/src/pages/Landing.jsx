import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ArrowRight,
  Code2,
  MessageSquare,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Target,
} from 'lucide-react'
import { Logo } from '../components/Logo.jsx'
import { Card } from '../components/ui.jsx'

const FEATURES = [
  {
    icon: Code2,
    title: 'Technical, scored fairly',
    body: 'Your reasoning is judged on the ideas you get right — not on fancy words.',
  },
  {
    icon: MessageSquare,
    title: 'Communication, scored separately',
    body: 'Clarity and structure are coached on their own track, never mixed with correctness.',
  },
  {
    icon: ScanSearch,
    title: 'Evidence you can see',
    body: 'Every result points to the exact lines in your answer that earned it.',
  },
  {
    icon: Target,
    title: 'Fix what matters',
    body: 'Real, recurring gaps are surfaced — never one-off slips or missing detail dressed up as errors.',
  },
]

export default function Landing() {
  return (
    <div className="min-h-screen bg-ink-950 dotted-grid">
      {/* ambient glow */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[480px] bg-[radial-gradient(60%_60%_at_50%_0%,rgba(139,92,246,0.18),transparent)]" />

      <header className="relative mx-auto flex max-w-6xl items-center justify-between px-5 py-5">
        <Logo />
        <Link to="/register" className="btn-primary">
          Get started <ArrowRight size={16} />
        </Link>
      </header>

      <main className="relative mx-auto max-w-6xl px-5">
        {/* Hero */}
        <section className="grid items-center gap-10 py-14 lg:grid-cols-2 lg:py-20">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <div className="chip bg-brand-soft text-brand-violet">
              <Sparkles size={14} /> Fair, explainable interview practice
            </div>
            <h1 className="mt-4 text-4xl font-extrabold leading-tight tracking-tight text-white sm:text-5xl">
              Practice smarter.
              <br />
              Communicate <span className="gradient-text">confidently.</span>
              <br />
              Build your career.
            </h1>
            <p className="mt-5 max-w-lg text-base leading-relaxed text-slate-400">
              CareerLift AI runs realistic technical interviews and gives you feedback that separates
              what you know from how you said it — so plain English never hides real skill.
            </p>
            <div className="mt-7 flex flex-wrap items-center gap-3">
              <Link to="/register" className="btn-primary !px-5 !py-3">
                Start practicing <ArrowRight size={16} />
              </Link>
              <a href="#fairscore" className="btn-ghost !px-5 !py-3">
                How FairScore works
              </a>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.97 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.6, delay: 0.1 }}
          >
            <Card glow className="p-6">
              <div className="mb-4 flex items-center justify-between">
                <span className="section-title">Sample result</span>
                <span className="chip bg-white/10 text-slate-300">Two independent scores</span>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-xl border border-white/5 bg-ink-900/70 p-4">
                  <div className="flex items-center gap-2 text-slate-300">
                    <Code2 size={16} className="text-brand-violet" />
                    <span className="text-sm font-semibold">Technical</span>
                  </div>
                  <p className="mt-3 text-2xl font-extrabold text-good">Solid</p>
                  <p className="mt-1 text-xs text-slate-500">Correct core idea, one gap.</p>
                </div>
                <div className="rounded-xl border border-white/5 bg-ink-900/70 p-4">
                  <div className="flex items-center gap-2 text-slate-300">
                    <MessageSquare size={16} className="text-brand-blue" />
                    <span className="text-sm font-semibold">Communication</span>
                  </div>
                  <p className="mt-3 text-2xl font-extrabold text-warn">Partial</p>
                  <p className="mt-1 text-xs text-slate-500">Clear, could be better organised.</p>
                </div>
              </div>
              <div className="mt-4 flex items-start gap-2 rounded-xl border border-good/15 bg-good/5 p-3 text-xs text-slate-300">
                <ShieldCheck size={16} className="mt-0.5 shrink-0 text-good" />
                Simple English, grammar slips, or a short answer never lower your technical score.
              </div>
            </Card>
          </motion.div>
        </section>

        {/* FairScore explainer */}
        <section id="fairscore" className="scroll-mt-10 py-10">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-2xl font-bold text-white sm:text-3xl">
              What makes CareerLift <span className="gradient-text">fair</span>
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-slate-400">
              Most tools blend "did you know it?" with "did you say it well?" into one number — which
              quietly punishes students who think clearly but write plainly. CareerLift keeps the two
              apart, on purpose.
            </p>
          </div>
          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {FEATURES.map((f, i) => (
              <motion.div
                key={f.title}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.05 }}
              >
                <Card className="h-full p-5">
                  <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand-soft text-brand-violet">
                    <f.icon size={18} />
                  </span>
                  <h3 className="mt-3 text-sm font-semibold text-white">{f.title}</h3>
                  <p className="mt-1.5 text-xs leading-relaxed text-slate-400">{f.body}</p>
                </Card>
              </motion.div>
            ))}
          </div>
        </section>

        {/* CTA */}
        <section className="py-14">
          <Card glow className="relative overflow-hidden px-6 py-10 text-center sm:px-10">
            <div className="pointer-events-none absolute inset-0 bg-brand-soft opacity-50" />
            <div className="relative">
              <h2 className="text-2xl font-bold text-white sm:text-3xl">Ready to practice?</h2>
              <p className="mx-auto mt-2 max-w-md text-sm text-slate-300">
                Create a free anonymous practice account in one click. No email, no password.
              </p>
              <Link to="/register" className="btn-primary mt-6 !px-6 !py-3">
                Create my practice account <ArrowRight size={16} />
              </Link>
            </div>
          </Card>
        </section>
      </main>

      <footer className="relative border-t border-white/5 py-6 text-center text-xs text-slate-600">
        CareerLift AI — built for students who deserve a fair read on their skills.
      </footer>
    </div>
  )
}
