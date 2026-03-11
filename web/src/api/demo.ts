/* Demo mode (VITE_DEMO=1): serves a captured 30-day dataset from memory so the
   dashboard runs with no backend at all — GitHub Pages, a USB stick, anywhere.
   Mutations (ack, device create) act on the in-memory copy for the session. */
import raw from './demoData.json'
import type { Anomaly, DailyPoint, Device } from './client'

export const DEMO = import.meta.env.VITE_DEMO === '1'

if (DEMO && !localStorage.getItem('baseline_jwt')) {
  localStorage.setItem('baseline_jwt', 'demo-token') // auto-login for the demo link
}

const state = {
  anomalies: structuredClone(raw.anomalies) as Anomaly[],
  devices: structuredClone(raw.devices) as Device[],
}

export async function demoApi<T>(path: string, init: RequestInit = {}): Promise<T> {
  await new Promise((r) => setTimeout(r, 120)) // a hint of network latency
  const method = (init.method ?? 'GET').toUpperCase()
  const [p, query] = path.split('?')
  const params = new URLSearchParams(query)

  if (method === 'POST' && (p === '/auth/login' || p === '/auth/register')) {
    return { access_token: 'demo-token', token_type: 'bearer' } as T
  }
  if (p === '/me') return raw.me as T
  if (p === '/devices' && method === 'GET') return state.devices as T
  if (p === '/devices' && method === 'POST') {
    const body = JSON.parse(String(init.body ?? '{}')) as { name?: string }
    const device: Device = {
      id: `demo-${Date.now()}`,
      name: body.name ?? 'Demo Device',
      created_at: new Date().toISOString(),
      last_seen_at: null,
    }
    state.devices = [...state.devices, device]
    return {
      ...device,
      device_token: 'bld_demo_' + Math.random().toString(36).slice(2, 14),
    } as T
  }
  if (p === '/anomalies' && method === 'GET') {
    const status = params.get('status')
    const list = status
      ? state.anomalies.filter((a) => a.status === status)
      : state.anomalies
    return list as T
  }
  const ack = p.match(/^\/anomalies\/(.+)\/ack$/)
  if (ack && method === 'POST') {
    state.anomalies = state.anomalies.map((a) =>
      a.id === ack[1] ? { ...a, status: 'acked' } : a,
    )
    return { id: ack[1], status: 'acked' } as T
  }
  if (p === '/daily') {
    const metric = params.get('metric') ?? ''
    const daily = raw.daily as Record<string, DailyPoint[]>
    return (daily[metric] ?? []) as T
  }
  if (p === '/pipeline/run') {
    return { clean_rows: 138208, daily_rows: 120, events_created: 0 } as T
  }
  throw new Error(`demo mode: no handler for ${method} ${path}`)
}
