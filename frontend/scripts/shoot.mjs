// Screenshot harness for CareerLift AI. Drives the REAL running app (frontend 5174 -> backend 8001,
// mock mode) and captures every page. Seeds real data through the backend API so pages show
// populated states, not just empty ones. No fabricated UI values — everything comes from the backend.
import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'
import { setTimeout as sleep } from 'node:timers/promises'

const FRONT = 'http://localhost:5174'
const API = 'http://127.0.0.1:8001'
const OUT = 'screenshots'
mkdirSync(OUT, { recursive: true })

async function api(path, { method = 'GET', body, token } = {}) {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`${method} ${path} -> ${res.status} ${await res.text()}`)
  return res.status === 204 ? null : res.json()
}

// ---- 1. Register a demo student through the real backend ----
const reg = await api('/register', { method: 'POST', body: { display_name: 'Priya' } })
const token = reg.token
const studentId = reg.student_id
console.log('registered', studentId)

// ---- 2. Seed REAL data: several scored practice answers across topics ----
const seeds = [
  {
    topic: 'complexity',
    answer:
      'Big-O describes how the running time grows as the input gets larger. For a linear scan we look at every element once, so the time grows in proportion to n, which we write as O(n). Binary search halves the remaining range each step, so it is O(log n). The worst case and the average case can differ: quicksort is usually O(n log n) but its worst case is O(n^2) when the pivot is always the smallest element.',
  },
  {
    topic: 'search',
    answer:
      'Binary search works on sorted data. You look at the middle element, and if the target is smaller you search the left half, otherwise the right half. Each step throws away half of what is left, so it takes about log2(n) steps. It only works when the data is already sorted — on unsorted data you would miss values.',
  },
  {
    topic: 'hashing',
    answer:
      'A hash table stores keys by hashing them to a bucket. Lookups are fast on average, close to constant time. But if many keys collide into the same bucket the lookup slows down, so the worst case is not O(1).',
  },
  {
    topic: 'recursion',
    answer: 'Recursion is when a function calls itself. You need a base case so it stops.',
  },
]

for (const s of seeds) {
  const iv = await api('/interviews', { method: 'POST', token, body: { topic: s.topic, level: 'beginner', role: 'software engineer' } })
  await api('/score', {
    method: 'POST',
    token,
    body: { interview_id: iv.interview_id, question: iv.question, answer: s.answer, concept_token: [] },
  })
  console.log('scored', s.topic)
}

// ---- 3. Seed a completed Studio session ----
const studio = await api('/studio/sessions', {
  method: 'POST',
  token,
  body: { category: 'technical', difficulty: 'beginner', experience: 'student', duration_min: 20, num_questions: 3, topics: ['complexity', 'search'] },
})
const sid = studio.session_id
const sess = await api(`/studio/sessions/${sid}`, { token })
for (const q of sess.questions) {
  await api(`/studio/sessions/${sid}/answer`, {
    method: 'POST',
    token,
    body: {
      question_id: q.question_id,
      answer:
        'The key idea is to reason about how the work scales with the input size and pick the approach that keeps that growth small. For sorted data a halving search is efficient, and we should always confirm the data is sorted first.',
    },
  })
}
await api(`/studio/sessions/${sid}/submit`, { method: 'POST', token })
console.log('studio completed', sid)

// ---- 4. Launch browser, inject session, screenshot every route ----
const browser = await chromium.launch()
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1024 }, deviceScaleFactor: 2 })
const page = await ctx.newPage()
const errors = []
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
page.on('pageerror', (e) => errors.push(String(e)))

// Pre-auth pages first (no session)
async function shoot(name, url, { waitFor } = {}) {
  await page.goto(`${FRONT}${url}`, { waitUntil: 'networkidle' })
  if (waitFor) { try { await page.waitForSelector(waitFor, { timeout: 8000 }) } catch {} }
  await sleep(900) // let framer-motion settle
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true })
  console.log('shot', name, '->', url)
}

await shoot('01-landing', '/')
await shoot('02-register', '/register')

// Inject the real session so Protected routes render with real data
await page.addInitScript(([sid, tok]) => {
  localStorage.setItem('careerlift.session', JSON.stringify({ student_id: sid, token: tok }))
}, [studentId, token])

const routes = [
  ['03-dashboard', '/app'],
  ['04-interview-studio', '/app/interview'],
  ['05-studio-session-results', `/app/interview/session/${sid}`],
  ['06-quick-practice', '/app/practice'],
  ['07-my-progress', '/app/progress'],
  ['08-misconceptions', '/app/misconceptions'],
  ['09-learning-planner', '/app/planner'],
  ['10-reports', '/app/reports'],
]
for (const [name, url] of routes) await shoot(name, url)

await browser.close()
console.log('\nConsole errors during run:', errors.length)
for (const e of errors) console.log('  -', e)
console.log('DONE. student=', studentId, 'studioSession=', sid)
