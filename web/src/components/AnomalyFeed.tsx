import { api } from '../api/client'
import type { Anomaly } from '../api/client'

interface Props {
  anomalies: Anomaly[]
  onChanged: () => void
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
            <span className={`sev sev-${a.severity}`}>{a.severity}</span>
            <span>{a.detector}</span>
            <span>{a.metric ?? 'multivariate'}</span>
            <span>from {a.started_at}</span>
            <span>({a.status})</span>
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
