// Mastery label -> visual helpers. Labels come from the backend (deterministic FairScore-driven model).
// No fabricated percentages: bars encode the LABEL's ordinal position, shown with the label text.

export const MASTERY_LABELS = ['Not enough evidence', 'Emerging', 'Developing', 'Proficient', 'Strong']

export function masteryMeta(label) {
  switch (label) {
    case 'Strong':
      return { ordinal: 4, pct: 100, hex: '#34d399', tone: 'good' }
    case 'Proficient':
      return { ordinal: 3, pct: 78, hex: '#4ade80', tone: 'good' }
    case 'Developing':
      return { ordinal: 2, pct: 52, hex: '#fbbf24', tone: 'warn' }
    case 'Emerging':
      return { ordinal: 1, pct: 28, hex: '#f59e0b', tone: 'warn' }
    default:
      return { ordinal: 0, pct: 6, hex: '#64748b', tone: 'muted' }
  }
}

// Friendly action verbs for a recommendation's `action`.
export function actionLabel(action) {
  return { revise: 'Revise', practice: 'Practise', assess: 'Assess', learn: 'Learn' }[action] || 'Practise'
}
