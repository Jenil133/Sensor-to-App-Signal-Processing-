import { api } from '../api/client'
import type { Anomaly } from '../api/client'

interface Props {
  anomalies: Anomaly[]
  onChanged: () => void
}

const SEV_ICON: Record<string, string> = { low: '●', med: '▲', high: '■' }

const DETECTOR_LABEL: Record<string, string> = {
  zscore: 'Z-score',
  cusum: 'CUSUM',
  isolation_forest: 'Isolation Forest',
  autoencoder: 'Autoencoder',
}

export default function AnomalyFeed({ anomalies, onChanged }: Props) {
  async function ack(id: string) {
    await api(`/anomalies/${id}/ack`, { method: 'POST' })
    onChanged()
  }

  return (
    <div className="card">
      <h3>Anomalies</h3>
      {anomalies.length === 0 ? (
        <div className="empty-note">nothing detected — that's a good thing</div>
      ) : (
        anomalies.map((a) => (
          <div className="feed-item" key={a.id}>
            <span className={`sev sev-${a.severity}`}>
              <span aria-hidden>{SEV_ICON[a.severity] ?? '●'}</span>
              {a.severity}
            </span>
            <span className="feed-detector">
              {DETECTOR_LABEL[a.detector] ?? a.detector}
            </span>
            <span className="feed-metric">{a.metric ?? 'multivariate'}</span>
            <span className="feed-when">
              {a.started_at}
              {a.ended_at ? ` → ${a.ended_at}` : ''}
            </span>
            <span className="feed-status">{a.status}</span>
            {a.status === 'open' && (
              <button className="ack-btn" onClick={() => ack(a.id)}>
                Acknowledge
              </button>
            )}
          </div>
        ))
      )}
    </div>
  )
}
