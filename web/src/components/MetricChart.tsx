import {
  Area,
  ComposedChart,
  Line,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Anomaly, DailyPoint } from '../api/client'

interface Props {
  title: string
  metric: string
  rows: DailyPoint[]
  anomalies: Anomaly[]
}

// Recharts renders a range area when the dataKey yields a [low, high] array.
export default function MetricChart({ title, metric, rows, anomalies }: Props) {
  const data = rows.map((r) => ({
    day: r.day,
    value: r.value,
    band:
      r.baseline_center != null && r.baseline_spread != null
        ? [
            r.baseline_center - 2 * r.baseline_spread,
            r.baseline_center + 2 * r.baseline_spread,
          ]
        : undefined, // ±2·spread "normal zone"
  }))
  const valueOn = (day: string) => rows.find((r) => r.day === day)?.value
  const dots = anomalies.filter(
    (a) => a.metric === metric && valueOn(a.started_at) !== undefined,
  )

  return (
    <div className="card">
      <h3>{title}</h3>
      {rows.length === 0 ? (
        <div className="empty-note">no data yet — run the simulator</div>
      ) : (
        <div style={{ height: 220 }}>
          <ResponsiveContainer>
            <ComposedChart data={data}>
              <XAxis dataKey="day" tick={{ fontSize: 11 }} minTickGap={24} />
              <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11 }} width={48} />
              <Tooltip />
              <Area
                dataKey="band"
                fill="#8884d8"
                fillOpacity={0.15}
                stroke="none"
                isAnimationActive={false}
              />
              <Line dataKey="value" dot={false} stroke="#888" strokeWidth={1.8} />
              {dots.map((a) => (
                <ReferenceDot
                  key={a.id}
                  x={a.started_at}
                  y={valueOn(a.started_at)}
                  r={5}
                  fill={a.severity === 'high' ? '#d9534f' : '#f0ad4e'}
                  stroke="none"
                />
              ))}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
