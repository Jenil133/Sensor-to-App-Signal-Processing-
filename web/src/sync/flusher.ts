import { peekAll, remove } from './queue'

export interface DrainReport {
  sent: number
  dropped: number
  lastError: string | null
}

type DrainListener = (report: DrainReport) => void

let draining = false
let started = false
const listeners = new Set<DrainListener>()

export function onDrain(fn: DrainListener): () => void {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

export async function drain(): Promise<void> {
  if (draining || !navigator.onLine) return
  draining = true
  const report: DrainReport = { sent: 0, dropped: 0, lastError: null }
  try {
    const items = await peekAll() // oldest first (autoincrement key order)
    for (const item of items) {
      let res: Response
      try {
        res = await fetch('/api/v1/ingest', {
          method: 'POST',
          headers: {
            'content-type': 'application/json',
            'X-Device-Token': item.deviceToken,
          },
          body: JSON.stringify(item.batch),
        })
      } catch {
        break // network error: stop draining, keep order, retry next cycle
      }
      if (res.status === 202) {
        await remove(item.id!)
        report.sent += 1
      } else if (res.status === 429) {
        break // rate-limited, NOT poison: halt in order, retry next cycle
      } else if (res.status >= 400 && res.status < 500) {
        // poison batch (revoked token, validation): retrying forever helps no one
        await remove(item.id!)
        report.dropped += 1
        report.lastError = `batch dropped: HTTP ${res.status}`
      } else {
        break // 5xx: server-side trouble, retry next cycle in order
      }
    }
  } finally {
    draining = false
    if (report.sent || report.dropped) listeners.forEach((fn) => fn(report))
  }
}

export function startFlusher(): void {
  if (started) return // idempotent
  started = true
  window.addEventListener('online', () => void drain())
  setInterval(() => void drain(), 15_000)
  void drain()
}
