// Phase 3 Technical Assessment — static UI copy + grade/difficulty mapping. No fabricated data: every
// score, count and timing in the UI comes straight from the backend result payload.
import {
  Boxes, Coffee, Terminal, Binary, Braces, Database, Table2, Cpu,
  Network, Layers, CircuitBoard, FileCode2, Shuffle,
} from 'lucide-react'

// Category id -> label + icon. Mirrors the backend catalog ids.
export const CATEGORY_META = {
  dsa: { label: 'Data Structures & Algorithms', icon: Boxes },
  java: { label: 'Java', icon: Coffee },
  python: { label: 'Python', icon: Terminal },
  c: { label: 'C', icon: Binary },
  cpp: { label: 'C++', icon: Braces },
  dbms: { label: 'DBMS', icon: Database },
  sql: { label: 'SQL', icon: Table2 },
  os: { label: 'Operating Systems', icon: Cpu },
  networks: { label: 'Computer Networks', icon: Network },
  oop: { label: 'Object-Oriented Programming', icon: Layers },
  architecture: { label: 'Computer Architecture', icon: CircuitBoard },
  software_engineering: { label: 'Software Engineering', icon: FileCode2 },
  mixed: { label: 'Mixed Technical', icon: Shuffle },
}

export function categoryMeta(id) {
  return CATEGORY_META[id] || { label: id, icon: FileCode2 }
}

export function categoryLabel(id) {
  return categoryMeta(id).label
}

export const DIFFICULTY_META = {
  beginner: { label: 'Beginner', hex: '#22c55e' },
  intermediate: { label: 'Intermediate', hex: '#f97316' },
  advanced: { label: 'Advanced', hex: '#f87171' },
  mixed: { label: 'Mixed', hex: '#8b5cf6' },
}

export function difficultyMeta(id) {
  return DIFFICULTY_META[id] || { label: id, hex: '#64748b' }
}

// Letter grade -> tone/colour (matches the backend's deterministic bands).
export const GRADE_META = {
  A: { hex: '#34d399', tone: 'good' },
  B: { hex: '#4ade80', tone: 'good' },
  C: { hex: '#fbbf24', tone: 'warn' },
  D: { hex: '#f97316', tone: 'warn' },
  F: { hex: '#f87171', tone: 'bad' },
}

export function gradeMeta(g) {
  return GRADE_META[g] || { hex: '#64748b', tone: 'muted' }
}

export function formatClock(totalSec) {
  const s = Math.max(0, Math.floor(totalSec))
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`
}

export function questionTypeLabel(t) {
  return { single: 'Single choice', multi: 'Multiple select', tf: 'True / False' }[t] || t
}
