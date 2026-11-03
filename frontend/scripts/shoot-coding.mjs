// Screenshot harness for the Phase 2 Coding Arena pages. Drives the REAL app (frontend 5174 -> backend
// 8001, mock mode). Seeds one coding submission via the real API so the list + detail show real state.
// NOTE: with Docker down, /coding/submit returns 503 (fail-closed), so we seed a submission row directly
// through the DB-independent path is not possible from the browser — instead we just screenshot the
// browse/editor states, which is what a user without Docker sees. The sandbox banner is expected.
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
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`${method} ${path} -> ${res.status} ${await res.text()}`)
  return res.status === 204 ? null : res.json()
}

const reg = await api('/register', { method: 'POST', body: { display_name: 'Coder' } })
const token = reg.token
const studentId = reg.student_id
console.log('registered', studentId)

const browser = await chromium.launch()
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1024 }, deviceScaleFactor: 2 })
const page = await ctx.newPage()
const errors = []
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
page.on('pageerror', (e) => errors.push(String(e)))

await page.addInitScript(([sid, tok]) => {
  localStorage.setItem('careerlift.session', JSON.stringify({ student_id: sid, token: tok }))
}, [studentId, token])

async function shoot(name, url) {
  await page.goto(`${FRONT}${url}`, { waitUntil: 'networkidle' })
  await sleep(900)
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true })
  console.log('shot', name, '->', url)
}

await shoot('11-coding-arena', '/app/coding')
await shoot('12-coding-problem', '/app/coding/P-BINARY-SEARCH')

await browser.close()
console.log('\nConsole errors during run:', errors.length)
for (const e of errors) console.log('  -', e)
console.log('DONE. student=', studentId)
