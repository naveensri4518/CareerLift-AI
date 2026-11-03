import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { EmptyState } from './ui.jsx'
import { bandMeta, BANDS } from '../lib/content.js'

// Plots the ORDINAL of each interview's bands over attempts. The y-axis is the four-band scale
// (Weak..Strong), never an invented 0-100 score. Abstained axes are gaps (null), not zeros.
export function ProgressChart({ history }) {
  const scored = (history || []).filter(
    (h) => (!h.abstained_technical && h.technical_band) || (!h.abstained_communication && h.communication_band),
  )

  if (scored.length < 1) {
    return (
      <EmptyState
        title="No trend yet"
        hint="Complete a few interviews and your Technical and Communication bands will chart here."
      />
    )
  }

  const data = scored.map((h, i) => ({
    name: `#${i + 1}`,
    technical: h.abstained_technical ? null : bandMeta(h.technical_band).ordinal || null,
    communication: h.abstained_communication ? null : bandMeta(h.communication_band).ordinal || null,
  }))

  const tickFmt = (v) => BANDS[v - 1] || ''

  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: -8 }}>
          <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
          <XAxis dataKey="name" stroke="#64748b" fontSize={11} tickLine={false} axisLine={false} />
          <YAxis
            domain={[0, 4]}
            ticks={[1, 2, 3, 4]}
            tickFormatter={tickFmt}
            stroke="#64748b"
            fontSize={11}
            tickLine={false}
            axisLine={false}
            width={64}
          />
          <Tooltip
            contentStyle={{
              background: '#100e1c',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 12,
              fontSize: 12,
            }}
            labelStyle={{ color: '#cbd5e1' }}
            formatter={(value, key) => [value ? BANDS[value - 1] : 'Not assessed', key === 'technical' ? 'Technical' : 'Communication']}
          />
          <Line
            type="monotone"
            dataKey="technical"
            stroke="#a78bfa"
            strokeWidth={2.5}
            dot={{ r: 3, fill: '#a78bfa' }}
            connectNulls
            isAnimationActive
          />
          <Line
            type="monotone"
            dataKey="communication"
            stroke="#3b82f6"
            strokeWidth={2.5}
            dot={{ r: 3, fill: '#3b82f6' }}
            connectNulls
            isAnimationActive
          />
        </LineChart>
      </ResponsiveContainer>
      <div className="mt-2 flex items-center justify-center gap-5 text-xs text-slate-400">
        <span className="flex items-center gap-1.5"><i className="h-2 w-2 rounded-full bg-brand-violet" /> Technical</span>
        <span className="flex items-center gap-1.5"><i className="h-2 w-2 rounded-full bg-brand-blue" /> Communication</span>
      </div>
    </div>
  )
}
