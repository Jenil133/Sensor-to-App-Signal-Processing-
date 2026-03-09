/* Client-side signal model for the in-browser Demo Device — same shapes as the
   Python simulator (circadian HR, warm nights on skin temp, night-high HRV,
   daytime motion bursts) so the server pipeline treats both identically. */

export interface GeneratedSample {
  metric: string
  ts: string // minute-aligned UTC ISO with Z — server dedupe depends on it
  value: number
}

export function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function gaussian(rng: () => number): number {
  // Box–Muller; rng() can return 0, guard the log
  const u = Math.max(rng(), 1e-12)
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * rng())
}

function minuteAlignedIso(ms: number): string {
  const d = new Date(Math.floor(ms / 60_000) * 60_000)
  return d.toISOString().replace(/\.\d{3}Z$/, 'Z')
}

/** Samples for the `minutes` minutes ending at nowMs (most recent last). */
export function generateTick(nowMs: number, minutes: number): GeneratedSample[] {
  const samples: GeneratedSample[] = []
  for (let i = minutes - 1; i >= 0; i--) {
    const ms = nowMs - i * 60_000
    const aligned = Math.floor(ms / 60_000) * 60_000
    const rng = mulberry32(aligned / 60_000) // deterministic per minute
    const d = new Date(aligned)
    const minuteOfDay = d.getUTCHours() * 60 + d.getUTCMinutes()
    const ts = minuteAlignedIso(aligned)

    let hr = 65 + 7 * Math.sin((2 * Math.PI * (minuteOfDay - 600)) / 1440)
    hr += gaussian(rng) * 2
    if (rng() < 0.003) hr += rng() < 0.5 ? -40 : 40 // motion-artifact spikes
    samples.push({ metric: 'heart_rate', ts, value: Math.round(hr * 100) / 100 })

    let temp = 33.3 + 0.3 * Math.cos((2 * Math.PI * (minuteOfDay - 120)) / 1440)
    temp += gaussian(rng) * 0.15
    samples.push({ metric: 'skin_temp', ts, value: Math.round(temp * 1000) / 1000 })

    if (minuteOfDay % 5 === 0) {
      let hrv = 45 + 10 * Math.cos((2 * Math.PI * (minuteOfDay - 180)) / 1440)
      hrv += gaussian(rng) * 8
      samples.push({ metric: 'hrv_rmssd', ts, value: Math.round(hrv * 100) / 100 })
    }

    const daytime = minuteOfDay >= 7 * 60 && minuteOfDay < 22 * 60
    const motion = daytime && rng() < 0.35 ? 100 + rng() * 700 : rng() * 3
    samples.push({ metric: 'motion', ts, value: Math.round(motion * 10) / 10 })
  }
  return samples
}
