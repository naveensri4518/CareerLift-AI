// Product copy and mappings. These are STATIC, curated descriptions (not performance data).
// Internal concept ids are mapped to friendly titles so ids never appear in the UI.

// Topics the backend understands (must match the server's known topic set).
export const TOPICS = [
  { id: 'complexity', label: 'Time Complexity (Big-O)', blurb: 'Reason about how algorithms scale.' },
  { id: 'search', label: 'Binary Search', blurb: 'Searching efficiently in sorted data.' },
  { id: 'hashing', label: 'Hash Tables', blurb: 'Fast lookups and their trade-offs.' },
  { id: 'recursion', label: 'Recursion', blurb: 'Base cases and recursive thinking.' },
  { id: 'sql-joins', label: 'SQL Joins', blurb: 'INNER vs LEFT joins and when to use them.' },
  { id: 'sql-index', label: 'Database Indexes', blurb: 'Speeding up reads and the cost of writes.' },
  { id: 'python', label: 'Python Pitfalls', blurb: 'Common Python gotchas in interviews.' },
]

export const LEVELS = [
  { id: 'beginner', label: 'Beginner' },
  { id: 'intermediate', label: 'Intermediate' },
  { id: 'advanced', label: 'Advanced' },
]

export function topicLabel(id) {
  return TOPICS.find((t) => t.id === id)?.label || prettyTopic(id)
}

function prettyTopic(id) {
  if (!id) return 'Practice'
  return String(id)
    .split('-')
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join(' ')
}

// Misconception tag -> friendly title + beginner explanation + the concept it relates to.
// Text mirrors the curated concept reference (definitions), not any student's data.
export const MISCONCEPTIONS = {
  'M-BIGO-AVG-WORST': {
    title: 'Average vs worst case',
    topic: 'complexity',
    explain:
      'Average-case and worst-case running time are not the same. Some algorithms are fast on typical inputs but slow on the worst input.',
  },
  'M-BINSEARCH-UNSORTED': {
    title: 'Binary search needs sorted data',
    topic: 'search',
    explain:
      'Binary search only works when the data is already sorted. On unsorted data it can miss the value entirely.',
  },
  'M-HASH-ALWAYS-O1': {
    title: 'Hash lookups are not always O(1)',
    topic: 'hashing',
    explain:
      'A hash table lookup is usually fast (constant time on average), but in the worst case — many collisions — it can be much slower.',
  },
  'M-RECURSION-NOBASE': {
    title: 'Recursion needs a base case',
    topic: 'recursion',
    explain:
      'A recursive function must have a base case that stops the recursion. Without one it calls itself forever and crashes.',
  },
  'M-JOIN-INNER-LEFT': {
    title: 'INNER JOIN vs LEFT JOIN',
    topic: 'sql-joins',
    explain:
      'An INNER JOIN keeps only matching rows; a LEFT JOIN keeps every row from the left table, filling gaps with NULLs. They are not interchangeable.',
  },
  'M-INDEX-FREE': {
    title: 'Indexes are not free',
    topic: 'sql-index',
    explain:
      'An index speeds up reads, but it adds cost to inserts and updates and uses extra space. It is a trade-off, not a free win.',
  },
  'M-MUTABLE-DEFAULT': {
    title: 'Mutable default arguments',
    topic: 'python',
    explain:
      'A mutable default argument (like []) is created once and shared across every call, which causes surprising bugs.',
  },
}

export function misconceptionInfo(tag) {
  return (
    MISCONCEPTIONS[tag] || {
      title: prettyTopic(tag).replace(/^M /, ''),
      topic: null,
      explain: 'A recurring gap detected across your answers. Revisit the related concept and try a fresh question.',
    }
  )
}

// Four-band scale -> ordinal, colour and label. The backend NEVER returns numeric scores,
// so the UI shows bands honestly and maps them to a visual position only.
export const BANDS = ['Weak', 'Partial', 'Solid', 'Strong']

export function bandMeta(band) {
  switch (band) {
    case 'Strong':
      return { label: 'Strong', ordinal: 4, pct: 100, tone: 'good', hex: '#34d399' }
    case 'Solid':
      return { label: 'Solid', ordinal: 3, pct: 72, tone: 'good', hex: '#4ade80' }
    case 'Partial':
      return { label: 'Partial', ordinal: 2, pct: 45, tone: 'warn', hex: '#fbbf24' }
    case 'Weak':
      return { label: 'Weak', ordinal: 1, pct: 20, tone: 'bad', hex: '#f87171' }
    default:
      return { label: 'Not assessed', ordinal: 0, pct: 0, tone: 'muted', hex: '#64748b' }
  }
}

// Relative frequency label for a misconception count (NOT a fabricated severity score).
export function frequencyLabel(count) {
  if (count >= 3) return { label: 'Frequent', tone: 'bad' }
  if (count === 2) return { label: 'Recurring', tone: 'warn' }
  return { label: 'Seen once', tone: 'muted' }
}
