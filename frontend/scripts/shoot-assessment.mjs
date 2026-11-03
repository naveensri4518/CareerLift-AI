// Screenshot harness for Phase 3 Technical Assessment pages. Drives the REAL app (frontend 5174 ->
// backend 8001, mock mode). Seeds a full attempt via the API so the Interface and Results pages show
// real state (real questions, a real graded result, real review).
import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'
import { setTimeout as sleep } from 'node:timers/promises'

const FRONT = 'http://localhost:5174'
const API = 'http://127.0.0.1:8001'
const OUT = 'screenshots'
mkdirSync(OUT, { recursive: true })

async function api(path, { method = 'GET', body, token } = {}) {
  const res = await fetch(`${API}${path}`, {
    method, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`${method} ${path} -> ${res.status} ${await res.text()}`)
  return res.status === 204 ? null : res.json()
}

const reg = await api('/register', { method: 'POST', body: { display_name: 'Assessor' } })
const token = reg.token, studentId = reg.student_id
console.log('registered', studentId)

// Seed a completed attempt (python, 10 Q) answered partly, so Results has real analytics + review.
const started = await api('/assessment/attempts', { method: 'POST', token, body: { category: 'mixed', difficulty: 'mixed', num_questions: 10, duration_min: 20 } })
const inProgressId = started.attempt_id
// answer first 6 (first option / true) to produce a mix of correct/incorrect
const answers = {}
started.questions.slice(0, 6).forEach((q) => {
  answers[q.id] = q.type === 'tf' ? { bool: true } : { selected: [q.options[0].id] }
})
await api(`/assessment/attempts/${inProgressId}/answers`, { method: 'POST', token, body: { answers } })
// a SECOND attempt we leave submitted for the Results screenshot
const a2 = await api('/assessment/attempts', { method: 'POST', token, body: { category: 'python', difficulty: 'mixed', num_questions: 10, duration_min: 20 } })
const ans2 = {}
a2.questions.forEach((q, i) => { if (i % 2 === 0) ans2[q.id] = q.type === 'tf' ? { bool: true } : { selected: [q.options[0].id] } })
await api(`/assessment/attempts/${a2.attempt_id}/answers`, { method: 'POST', token, body: { answers: ans2 } })
await api(`/assessment/attempts/${a2.attempt_id}/submit`, { method: 'POST', token })
console.log('seeded: in-progress', inProgressId, 'submitted', a2.attempt_id)

const browser = await chromium.launch()
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1024 }, deviceScaleFactor: 2 })
const page = await ctx.newPage()
const errors = []
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
page.on('pageerror', (e) => errors.push(String(e)))
await page.addInitScript(([sid, tok]) => localStorage.setItem('careerlift.session', JSON.stringify({ student_id: sid, token: tok })), [studentId, token])

async function shoot(name, url) {
  await page.goto(`${FRONT}${url}`, { waitUntil: 'networkidle' })
  await sleep(1000)
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true })
  console.log('shot', name, '->', url)
}

await shoot('13-assessment-landing', '/app/assessment')
await shoot('14-assessment-attempt', `/app/assessment/attempt/${inProgressId}`)
await shoot('15-assessment-result', `/app/assessment/result/${a2.attempt_id}`)
await shoot('16-assessment-history', '/app/assessment/history')

await browser.close()
console.log('\nConsole errors:', errors.length)
for (const e of errors.slice(0, 10)) console.log('  -', e)
console.log('DONE')
