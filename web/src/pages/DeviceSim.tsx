import { useCallback, useEffect, useRef, useState } from 'react'
import { count, enqueue } from '../sync/queue'
import { drain, onDrain } from '../sync/flusher'
import { generateTick } from '../sync/generator'

const TOKEN_KEY = 'baseline_device_token'
const TICK_MS = 5_000
const BACKFILL_CAP_MIN = 6 * 60 // keeps any batch ≤ MAX_BATCH_SAMPLES after sleep

export default function DeviceSim() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) ?? '')
  const [running, setRunning] = useState(false)
  const [online, setOnline] = useState(navigator.onLine)
  const [queued, setQueued] = useState(0)
  const [generated, setGenerated] = useState(0)
  const [synced, setSynced] = useState(0)
  const [lastSync, setLastSync] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const lastTickRef = useRef<number>(Date.now())

  const refreshQueue = useCallback(async () => setQueued(await count()), [])

  useEffect(() => {
    const up = () => setOnline(true)
    const down = () => setOnline(false)
    window.addEventListener('online', up)
    window.addEventListener('offline', down)
    void refreshQueue()
    const unsub = onDrain((report) => {
      if (report.sent) {
        setSynced((n) => n + report.sent)
        setLastSync(new Date().toLocaleTimeString())
      }
      if (report.lastError) setError(report.lastError)
      void refreshQueue()
    })
    return () => {
      window.removeEventListener('online', up)
      window.removeEventListener('offline', down)
      unsub()
    }
  }, [refreshQueue])

  useEffect(() => {
    if (!running) return
    lastTickRef.current = Date.now()
    const id = setInterval(() => {
      void (async () => {
        const now = Date.now()
        const elapsedMin = Math.min(
          Math.floor((now - lastTickRef.current) / 60_000) + 1,
          BACKFILL_CAP_MIN,
        )
        lastTickRef.current = now
        const samples = generateTick(now, elapsedMin)
        setGenerated((n) => n + samples.length)
        await enqueue({
          createdAt: now,
          deviceToken: token,
          batch: { device_time: new Date(now).toISOString(), samples },
        })
        await refreshQueue()
        void drain()
      })()
    }, TICK_MS)
    return () => clearInterval(id)
  }, [running, token, refreshQueue])

  function saveToken(v: string) {
    setToken(v)
    localStorage.setItem(TOKEN_KEY, v)
  }

  return (
    <div>
      <h1 className="page-title">Demo Device</h1>
      <p className="sim-blurb">
        Generates telemetry in the browser, queues it in IndexedDB and syncs in
        the background — keep generating while offline, batches upload on their
        own when connectivity returns.
      </p>
      <div className="device-form">
        <input
          placeholder="paste a device token (bld_...)"
          value={token}
          onChange={(e) => saveToken(e.target.value)}
        />
        <button
          className="btn-primary"
          disabled={!token.startsWith('bld_')}
          onClick={() => {
            setError(null)
            setRunning(!running)
          }}
        >
          {running ? 'Stop' : 'Start'}
        </button>
      </div>
      {error && <div className="error-note">{error}</div>}
      <div className="stat-row">
        <div className="stat-tile">
          <div className="stat-label">Connection</div>
          <div className="stat-value">{online ? 'online' : 'offline'}</div>
          <div className={`stat-delta ${online ? 'ok' : 'warn'}`}>
            {online ? 'batches sync as generated' : 'queueing locally'}
          </div>
        </div>
        <div className="stat-tile">
          <div className="stat-label">Queued batches</div>
          <div className="stat-value">{queued}</div>
          <div className="stat-delta">waiting in IndexedDB</div>
        </div>
        <div className="stat-tile">
          <div className="stat-label">Samples generated</div>
          <div className="stat-value">{generated}</div>
          <div className="stat-delta">{running ? 'ticking every 5 s' : 'stopped'}</div>
        </div>
        <div className="stat-tile">
          <div className="stat-label">Batches synced</div>
          <div className="stat-value">{synced}</div>
          <div className="stat-delta">
            {lastSync ? `last sync ${lastSync}` : 'no sync yet'}
          </div>
        </div>
      </div>
    </div>
  )
}
