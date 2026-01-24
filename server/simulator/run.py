"""Sensor simulator CLI: generates noisy daily telemetry and POSTs it to /ingest.

Example:
    python -m simulator.run --api http://localhost:8000 --device-token bld_... \
        --days 2 --seed 42 --start 2026-07-01 [--inject-shift-day N]

Days are 1-based; from --inject-shift-day onward the physiological shift is
applied (HR +6 bpm, skin temp +0.6 °C, HRV −12 ms).
"""
import argparse
import sys
from datetime import date, datetime, timedelta, timezone

import httpx
import numpy as np

from simulator.generate import heart_rate_day, hrv_day, motion_day, skin_temp_day

SHIFT_BPM = 6.0
SHIFT_C = 0.6
SHIFT_HRV_MS = 12.0
BATCH_HOURS = 6


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def day_samples(rng: np.random.Generator, day_start: datetime, shifted: bool) -> list[dict]:
    hr = heart_rate_day(rng, shift_bpm=SHIFT_BPM if shifted else 0.0)
    temp = skin_temp_day(rng, shift_c=SHIFT_C if shifted else 0.0)
    hrv = hrv_day(rng, shift_ms=SHIFT_HRV_MS if shifted else 0.0)
    motion = motion_day(rng)
    samples = []
    for minute in range(1440):
        ts = iso_z(day_start + timedelta(minutes=minute))
        samples.append({"metric": "heart_rate", "ts": ts, "value": round(float(hr[minute]), 2)})
        samples.append({"metric": "skin_temp", "ts": ts, "value": round(float(temp[minute]), 3)})
        samples.append({"metric": "motion", "ts": ts, "value": round(float(motion[minute]), 1)})
        if minute % 5 == 0:
            samples.append({"metric": "hrv_rmssd", "ts": ts,
                            "value": round(float(hrv[minute // 5]), 2)})
    return samples


def main() -> int:
    parser = argparse.ArgumentParser(description="Baseline sensor simulator")
    parser.add_argument("--api", required=True, help="API base URL, e.g. http://localhost:8000")
    parser.add_argument("--device-token", required=True, help="bld_... token from device creation")
    parser.add_argument("--days", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--start", default=None,
                        help="UTC start date YYYY-MM-DD (default: today minus --days)")
    parser.add_argument("--inject-shift-day", type=int, default=None,
                        help="1-based day from which the physiological shift is injected")
    args = parser.parse_args()

    start_date = (date.fromisoformat(args.start) if args.start
                  else datetime.now(timezone.utc).date() - timedelta(days=args.days))
    rng = np.random.default_rng(args.seed)
    client = httpx.Client(base_url=args.api, timeout=60.0,
                          headers={"X-Device-Token": args.device_token})

    totals = {"stored": 0, "dropped_out_of_range": 0, "dropped_duplicates": 0}
    for day_idx in range(1, args.days + 1):
        day_start = datetime.combine(start_date + timedelta(days=day_idx - 1),
                                     datetime.min.time(), tzinfo=timezone.utc)
        shifted = args.inject_shift_day is not None and day_idx >= args.inject_shift_day
        samples = day_samples(rng, day_start, shifted)
        for batch_no in range(24 // BATCH_HOURS):
            lo = day_start + timedelta(hours=batch_no * BATCH_HOURS)
            hi = lo + timedelta(hours=BATCH_HOURS)
            batch = [s for s in samples if lo <= datetime.fromisoformat(s["ts"]) < hi]
            resp = client.post("/api/v1/ingest",
                               json={"device_time": iso_z(datetime.now(timezone.utc)),
                                     "samples": batch})
            if resp.status_code != 202:
                print(f"day {day_idx} batch {batch_no + 1}: HTTP {resp.status_code} "
                      f"{resp.text[:300]} — stopping", file=sys.stderr)
                return 1
            body = resp.json()
            for k in totals:
                totals[k] += body[k]
            print(f"day {day_idx}{' (shifted)' if shifted else ''} "
                  f"batch {batch_no + 1}/4: stored={body['stored']} "
                  f"dropped_range={body['dropped_out_of_range']} "
                  f"dupes={body['dropped_duplicates']}")
    print(f"done: {args.days} day(s) — stored={totals['stored']} "
          f"dropped_range={totals['dropped_out_of_range']} "
          f"dupes={totals['dropped_duplicates']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
