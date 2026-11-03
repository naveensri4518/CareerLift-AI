import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  BarChart3,
  Bot,
  CalendarClock,
  CircleUserRound,
  ClipboardList,
  Code2,
  FileText,
  LayoutDashboard,
  LogOut,
  Menu,
  Mic,
  Network,
  Target,
  X,
} from 'lucide-react'
import { Logo } from './Logo.jsx'
import { useAuth } from '../context/AuthContext.jsx'

const NAV = [
  { to: '/app', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/app/interview', label: 'Interview Studio', icon: Mic },
  { to: '/app/coding', label: 'Coding Arena', icon: Code2 },
  { to: '/app/assessment', label: 'Technical Assessment', icon: ClipboardList },
  { to: '/app/sysdesign', label: 'System Design', icon: Network },
  { to: '/app/practice', label: 'Quick Practice', icon: Target },
  { to: '/app/progress', label: 'My Progress', icon: BarChart3 },
  { to: '/app/misconceptions', label: 'Misconceptions', icon: Target },
  { to: '/app/planner', label: 'Learning Planner', icon: CalendarClock },
  { to: '/app/reports', label: 'Reports', icon: FileText },
]

function CoachCard() {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-brand-purple/20 bg-gradient-to-b from-brand-purple/15 to-transparent p-4">
      <div className="mb-2 grid h-12 w-12 place-items-center rounded-xl bg-ink-900/70">
        <Bot size={22} className="text-brand-violet" />
      </div>
      <p className="text-sm font-bold text-white">Your AI Interview Coach</p>
      <p className="mt-1 text-xs leading-relaxed text-slate-400">
        Practice, get fair scores, fix misconceptions, and grow with a learning plan.
      </p>
    </div>
  )
}

function SidebarContent({ onNavigate }) {
  return (
    <div className="flex h-full flex-col gap-6 p-4">
      <div className="px-1 pt-1">
        <Logo />
      </div>
      <nav className="flex flex-col gap-1">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={onNavigate}
            className={({ isActive }) => `nav-link ${isActive ? 'nav-link-active' : ''}`}
          >
            <item.icon size={18} />
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto">
        <CoachCard />
      </div>
    </div>
  )
}

export function AppLayout({ children }) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const { studentId, logout } = useAuth()
  const navigate = useNavigate()

  const shortId = studentId ? studentId.replace('stu_', '').slice(0, 6) : ''

  const onLogout = () => {
    logout()
    navigate('/')
  }

  return (
    <div className="min-h-screen bg-ink-950 dotted-grid">
      {/* Sidebar — desktop */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-white/5 bg-ink-900/60 lg:block">
        <SidebarContent />
      </aside>

      {/* Sidebar — mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setMobileOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 border-r border-white/5 bg-ink-900">
            <div className="flex justify-end p-2">
              <button className="btn-ghost !px-2 !py-2" onClick={() => setMobileOpen(false)} aria-label="Close menu">
                <X size={18} />
              </button>
            </div>
            <SidebarContent onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      <div className="lg:pl-64">
        {/* Topbar */}
        <header className="sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-white/5 bg-ink-950/80 px-4 py-3 backdrop-blur sm:px-6">
          <div className="flex items-center gap-3">
            <button
              className="btn-ghost !px-2 !py-2 lg:hidden"
              onClick={() => setMobileOpen(true)}
              aria-label="Open menu"
            >
              <Menu size={18} />
            </button>
            <div className="lg:hidden">
              <Logo compact />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-sm sm:flex">
              <span className="grid h-6 w-6 place-items-center rounded-full bg-brand-gradient text-[11px] font-bold text-white">
                S
              </span>
              <span className="text-slate-300">Student</span>
              {shortId ? <span className="text-slate-500">#{shortId}</span> : null}
            </div>
            <button className="btn-ghost" onClick={onLogout} title="Sign out">
              <LogOut size={16} />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        </header>

        <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6">{children}</main>
      </div>
    </div>
  )
}
