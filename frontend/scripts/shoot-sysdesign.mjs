// Screenshot harness for Phase 4 System Design Academy. Drives the REAL app (frontend 5174 -> backend
// 8001, mock mode). Seeds a submitted attempt with a strong design so Workspace + Result show real state.
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

const reg = await api('/register', { method: 'POST', body: { display_name: 'Architect' } })
const token = reg.token, studentId = reg.student_id
console.log('registered', studentId)

// in-progress attempt (for Workspace screenshot) with a partial design
const a1 = await api('/sysdesign/attempts', { method: 'POST', token, body: { scenario_id: 'SD-URL-SHORTENER' } })
await api(`/sysdesign/attempts/${a1.attempt_id}/design`, { method: 'POST', token, body: {
  components: ['app_server', 'cache', 'lb'],
  connections: [['app_server', 'cache'], ['lb', 'app_server']],
  decisions: { datastore: { selected: ['kv'] }, code_gen: { selected: ['counter_base62'] } },
} })

// a second attempt submitted with a strong design (for Result screenshot)
const a2 = await api('/sysdesign/attempts', { method: 'POST', token, body: { scenario_id: 'SD-IMAGE-UPLOAD' } })
await api(`/sysdesign/attempts/${a2.attempt_id}/design`, { method: 'POST', token, body: {
  components: ['app_server', 'object_store', 'message_queue', 'worker', 'cdn', 'lb'],
  connections: [['app_server', 'object_store'], ['app_server', 'message_queue'], ['message_queue', 'worker']],
  decisions: {
    storage: { selected: ['object_store'] }, processing: { selected: ['async_worker'] },
    delivery: { selected: ['cdn', 'cache_meta'] }, tradeoffs: { selected: ['async_latency', 'object_vs_blob', 'cdn_cost'] },
  },
} })
await api(`/sysdesign/attempts/${a2.attempt_id}/submit`, { method: 'POST', token })
console.log('seeded in-progress', a1.attempt_id, 'submitted', a2.attempt_id)

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

await shoot('17-sysdesign-academy', '/app/sysdesign')
await shoot('18-sysdesign-workspace', `/app/sysdesign/attempt/${a1.attempt_id}`)
await shoot('19-sysdesign-result', `/app/sysdesign/result/${a2.attempt_id}`)
await shoot('20-sysdesign-history', '/app/sysdesign/history')

await browser.close()
console.log('\nConsole errors:', errors.length)
for (const e of errors.slice(0, 10)) console.log('  -', e)
console.log('DONE')
