// Phase 4 System Design Academy — static UI metadata. No fabricated data: all scores/dimensions shown
// come straight from the backend result payload.
import {
  Monitor, Globe, Network, Server, Boxes, Database, HardDrive, Layers, Workflow, Cog, Search, Hash, Shield, Zap,
} from 'lucide-react'

export const DIFFICULTY_META = {
  beginner: { label: 'Beginner', hex: '#22c55e' },
  intermediate: { label: 'Intermediate', hex: '#f97316' },
  advanced: { label: 'Advanced', hex: '#f87171' },
}
export function difficultyMeta(id) {
  return DIFFICULTY_META[id] || { label: id, hex: '#64748b' }
}

// Component id -> icon for the palette/canvas.
export const COMPONENT_ICON = {
  client: Monitor, dns: Globe, cdn: Globe, lb: Network, api_gateway: Shield, app_server: Server,
  cache: Zap, sql_db: Database, nosql_db: Database, object_store: HardDrive, message_queue: Workflow,
  worker: Cog, search_index: Search, id_generator: Hash,
}
export function componentIcon(id) {
  return COMPONENT_ICON[id] || Boxes
}

// Rubric dimension -> friendly label.
export const DIMENSION_LABEL = {
  components: 'Component selection',
  connections: 'Connections',
  data: 'Database design',
  api: 'API design',
  scalability: 'Scalability',
  reliability: 'Reliability',
  tradeoffs: 'Trade-off analysis',
}
export function dimensionLabel(id) {
  return DIMENSION_LABEL[id] || id
}

export const GRADE_META = {
  A: { hex: '#34d399' }, B: { hex: '#4ade80' }, C: { hex: '#fbbf24' }, D: { hex: '#f97316' }, F: { hex: '#f87171' },
}
export function gradeMeta(g) {
  return GRADE_META[g] || { hex: '#64748b' }
}

export const DIMENSION_ICON = Layers
