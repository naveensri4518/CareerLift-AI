import { Rocket } from 'lucide-react'

export function Logo({ compact = false }) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand-gradient shadow-[0_6px_18px_-6px_rgba(99,102,241,0.9)]">
        <Rocket size={18} className="text-white" />
      </span>
      {!compact && (
        <div className="leading-tight">
          <div className="text-[15px] font-extrabold tracking-tight text-white">CareerLift AI</div>
          <div className="text-[10px] font-medium uppercase tracking-wider text-slate-500">
            AI-Powered Interview Preparation
          </div>
        </div>
      )}
    </div>
  )
}
