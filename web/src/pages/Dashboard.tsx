import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Anomaly, DailyPoint } from '../api/client'
import AnomalyFeed from '../components/AnomalyFeed'
import MetricChart from '../components/MetricChart'

const METRICS: { key: string; title: string }[] = [
  { key: 'resting_hr', title: 'Resting heart rate (bpm)' },
  { key: 'hrv_night', title: 'Night HRV — RMSSD (ms)' },
  { key: 'skin_temp_night', title: 'Night skin temperature (°C)' },
  { key: 'motion_total', title: 'Daily motion (counts)' },
]

function daysAgoIso(n: number): string {
  const d = new Date(Date.now() - n * 86_400_000)
  return d.toISOString().slice(0, 10)
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
      <div className="charts-grid">
        {METRICS.map((m) => (
          <MetricChart
            key={m.key}
            title={m.title}
            metric={m.key}
            rows={series[m.key] ?? []}
            anomalies={anomalies}
          />
        ))}
      </div>
      <div style={{ marginTop: '1.25rem' }}>
        <AnomalyFeed anomalies={anomalies} onChanged={() => void load()} />
      </div>
    </div>
  )
}
