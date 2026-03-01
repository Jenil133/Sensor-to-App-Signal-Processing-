import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Anomaly, DailyPoint } from '../api/client'
import AnomalyFeed from '../components/AnomalyFeed'
import MetricChart from '../components/MetricChart'

const METRICS: { key: string; title: string; unit: string; decimals: number }[] = [
  { key: 'resting_hr', title: 'Resting heart rate', unit: 'bpm', decimals: 1 },
  { key: 'hrv_night', title: 'Night HRV · RMSSD', unit: 'ms', decimals: 1 },
  { key: 'skin_temp_night', title: 'Night skin temperature', unit: '°C', decimals: 2 },
  { key: 'motion_total', title: 'Daily motion', unit: 'counts', decimals: 0 },
]

function daysAgoIso(n: number): string {
  const d = new Date(Date.now() - n * 86_400_000)
  return d.toISOString().slice(0, 10)
}

function StatTile({ title, unit, decimals, rows }: {
  title: string
  unit: string
  decimals: number
  rows: DailyPoint[]
}) {
  const latest = rows.at(-1)
  if (!latest) {
    return (
      <div className="stat-tile">
        <div className="stat-label">{title}</div>
        <div className="stat-value">—</div>
      </div>
    )
  }
  const z = latest.z
  const zClass = z == null || Math.abs(z) < 2 ? 'ok' : Math.abs(z) < 4 ? 'warn' : 'crit'
  const arrow = z == null ? '' : z > 0 ? '▲' : z < 0 ? '▼' : ''
  return (
    <div className="stat-tile">
      <div className="stat-label">{title}</div>
      <div className="stat-value">
        {latest.value.toFixed(decimals)}
        <span className="stat-unit">{unit}</span>
      </div>
      <div className={`stat-delta ${zClass}`}>
        {z == null ? (
          'building baseline'
        ) : (
          <>
            <span aria-hidden>{arrow}</span>
            {Math.abs(z).toFixed(1)}σ vs your baseline
          </>
        )}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [series, setSeries] = useState<Record<string, DailyPoint[]>>({})
  const [anomalies, setAnomalies] = useState<Anomaly[]>([])
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const start = daysAgoIso(60)
      const results = await Promise.all(
        METRICS.map((m) =>
          api<DailyPoint[]>(`/daily?metric=${m.key}&start=${start}`),
        ),
      )
      setSeries(Object.fromEntries(METRICS.map((m, i) => [m.key, results[i]])))
      setAnomalies(await api<Anomaly[]>('/anomalies'))
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'failed to load')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <div>
      {error && <div className="error-note">{error}</div>}
      <div className="stat-row">
        {METRICS.map((m) => (
          <StatTile
            key={m.key}
            title={m.title}
            unit={m.unit}
            decimals={m.decimals}
            rows={series[m.key] ?? []}
          />
        ))}
      </div>
      <div className="charts-grid">
        {METRICS.map((m) => (
          <MetricChart
            key={m.key}
            title={`${m.title} (${m.unit})`}
            metric={m.key}
            unit={m.unit}
            rows={series[m.key] ?? []}
            anomalies={anomalies}
          />
        ))}
      </div>
      <div className="section-gap">
        <AnomalyFeed anomalies={anomalies} onChanged={() => void load()} />
      </div>
    </div>
  )
}
