import { useEffect, useState } from 'react'

/* Chart colors must be concrete hex (SVG presentation attributes can't resolve
   CSS var()), so the same tokens App.css defines live here for Recharts. */
export interface ChartTheme {
  series: string
  band: string
  bandOpacity: number
  grid: string
  axisInk: string
  tooltipBg: string
  tooltipBorder: string
  tooltipInk: string
  statusWarning: string
  statusCritical: string
  surface: string
}

const LIGHT: ChartTheme = {
  series: '#2a78d6',
  band: '#9ec5f4',
  bandOpacity: 0.22,
  grid: '#e1e0d9',
  axisInk: '#898781',
  tooltipBg: '#fcfcfb',
  tooltipBorder: 'rgba(11,11,11,0.10)',
  tooltipInk: '#0b0b0b',
  statusWarning: '#fab219',
  statusCritical: '#d03b3b',
  surface: '#fcfcfb',
}

const DARK: ChartTheme = {
  series: '#3987e5',
  band: '#1c5cab',
  bandOpacity: 0.28,
  grid: '#2c2c2a',
  axisInk: '#898781',
  tooltipBg: '#1a1a19',
  tooltipBorder: 'rgba(255,255,255,0.10)',
  tooltipInk: '#ffffff',
  statusWarning: '#fab219',
  statusCritical: '#d03b3b',
  surface: '#1a1a19',
}

export function useChartTheme(): ChartTheme {
  const [dark, setDark] = useState(
    () => window.matchMedia('(prefers-color-scheme: dark)').matches,
  )
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = (e: MediaQueryListEvent) => setDark(e.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  return dark ? DARK : LIGHT
}
