import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Anomaly, DailyPoint } from '../api/client'
import { useChartTheme } from '../theme'

interface Props {
  title: string
  metric: string
  unit: string
  rows: DailyPoint[]
  anomalies: Anomaly[]
}

interface TooltipRow {
  value?: number
  payload?: { day: string; value: number; band?: [number, number] }
}

function ChartTip({ active, payload, unit }: {
  active?: boolean
  payload?: TooltipRow[]
  unit: string
}) {
  const row = payload?.find((p) => p.payload)?.payload
  if (!active || !row) return null
  return (
    <div className="chart-tooltip">
      <div className="tt-day">{row.day}</div>
      <div className="tt-value">
        {row.value.toFixed(1)} {unit}
      </div>
      {row.band && (
        <div className="tt-band">
          normal {row.band[0].toFixed(1)}–{row.band[1].toFixed(1)}
        </div>
      )}
    </div>
  )
}

// Recharts renders a range area when the dataKey yields a [low, high] array.
export default function MetricChart({ title, metric, unit, rows, anomalies }: Props) {
  const theme = useChartTheme()
  const data = rows.map((r) => ({
    day: r.day,
    value: r.value,
    band:
      r.baseline_center != null && r.baseline_spread != null
        ? ([
            r.baseline_center - 2 * r.baseline_spread,
            r.baseline_center + 2 * r.baseline_spread,
          ] as [number, number])
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
            <ComposedChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid
                stroke={theme.grid}
                strokeWidth={1}
                vertical={false}
              />
              <XAxis
                dataKey="day"
                tick={{ fontSize: 11, fill: theme.axisInk }}
                tickLine={false}
                axisLine={{ stroke: theme.grid }}
                minTickGap={28}
                tickFormatter={(d: string) => d.slice(5)}
              />
              <YAxis
                domain={['auto', 'auto']}
                tick={{ fontSize: 11, fill: theme.axisInk }}
                tickLine={false}
                axisLine={false}
                width={44}
                tickFormatter={(v: number) =>
                  Math.abs(v) >= 10_000 ? `${Math.round(v / 1000)}k` : String(v)
                }
              />
              <Tooltip
                content={<ChartTip unit={unit} />}
                cursor={{ stroke: theme.axisInk, strokeDasharray: '3 3' }}
              />
              <Area
                dataKey="band"
                fill={theme.band}
                fillOpacity={theme.bandOpacity}
                stroke="none"
                isAnimationActive={false}
              />
              <Line
                dataKey="value"
                dot={false}
                stroke={theme.series}
                strokeWidth={2}
                isAnimationActive={false}
              />
              {dots.map((a) => (
                <ReferenceDot
                  key={a.id}
                  x={a.started_at}
                  y={valueOn(a.started_at)}
                  r={5}
                  fill={a.severity === 'high' ? theme.statusCritical : theme.statusWarning}
                  stroke={theme.surface}
                  strokeWidth={2}
                />
              ))}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
