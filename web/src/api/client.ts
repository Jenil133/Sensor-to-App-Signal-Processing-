import { DEMO, demoApi } from './demo'

const TOKEN_KEY = 'baseline_jwt'
export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (t: string | null) =>
  t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY)

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (DEMO) return demoApi<T>(path, init)
  const headers: Record<string, string> = {
    'content-type': 'application/json',
    ...(init.headers as Record<string, string> | undefined),
  }
  const token = getToken()
  if (token) headers.authorization = `Bearer ${token}`
  const res = await fetch(`/api/v1${path}`, { ...init, headers })
  if (res.status === 401 && token) {
    // Session expired mid-use: clear and re-login. A 401 with NO token is a
    // failed login attempt — let the form show its error instead of reloading.
    setToken(null)
    window.location.assign('/login')
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(
      typeof body?.detail === 'string' ? body.detail : `HTTP ${res.status}`,
    )
  }
  return res.json() as Promise<T>
}

export interface DailyPoint {
  day: string
  value: number
  z: number | null
  baseline_center: number | null
  baseline_spread: number | null
}

export interface Anomaly {
  id: string
  metric: string | null
  detector: string
  severity: string
  score: number
  started_at: string
  ended_at: string | null
  status: string
  details: Record<string, unknown>
  created_at: string
}

export interface Device {
  id: string
  name: string
  created_at: string
  last_seen_at: string | null
}

export interface DeviceWithToken extends Device {
  device_token: string
}
