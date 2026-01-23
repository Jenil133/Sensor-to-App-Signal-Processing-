"""Realistic noisy one-day signal generators, one array per metric.

All generators take a seeded numpy Generator so runs are reproducible.
Shift parameters model a "coming down with something" physiological signature
(Phase 2's detectors must catch it): HR up, skin temp up, HRV down.
"""
import numpy as np


def heart_rate_day(rng: np.random.Generator, shift_bpm: float = 0.0) -> np.ndarray:
    """Per-minute heart rate (1440 values)."""
    m = np.arange(1440)
    # Circadian: trough ~04:00 (~58 bpm), daytime plateau (~72 bpm)
    hr = 65 + 7 * np.sin(2 * np.pi * (m - 600) / 1440)
    for _ in range(rng.integers(2, 5)):                    # activity bouts
        start = rng.integers(8 * 60, 21 * 60)
        dur = rng.integers(20, 45)
        hr[start:start + dur] += rng.uniform(25, 60)
    hr += rng.normal(0, 2.0, 1440)                         # sensor noise
    spikes = rng.random(1440) < 0.003                      # motion-artifact spikes
    hr[spikes] += rng.choice([-40, 40], spikes.sum())      #   (Hampel removes these in Phase 2)
    return hr + shift_bpm


def skin_temp_day(rng: np.random.Generator, shift_c: float = 0.0) -> np.ndarray:
    """Per-minute distal skin temperature (1440 values): ~33.6 °C at night, ~33.0 °C by day."""
    m = np.arange(1440)
    temp = 33.3 + 0.3 * np.cos(2 * np.pi * (m - 120) / 1440)   # peak ~02:00, trough ~14:00
    temp += rng.normal(0, 0.15, 1440)
    return temp + shift_c


def hrv_day(rng: np.random.Generator, shift_ms: float = 0.0) -> np.ndarray:
    """RMSSD every 5 minutes (288 values): night ~55 ms, day ~35 ms. Shift subtracts."""
    m = np.arange(288) * 5
    hrv = 45 + 10 * np.cos(2 * np.pi * (m - 180) / 1440)       # peak ~03:00
    hrv += rng.normal(0, 8.0, 288)
    return hrv - shift_ms


def motion_day(rng: np.random.Generator) -> np.ndarray:
    """Per-minute activity counts (1440 values): ~0 at night, daytime bursts 100–800."""
    counts = np.zeros(1440)
    daytime = np.arange(7 * 60, 22 * 60)
    active = rng.random(daytime.size) < 0.35
    counts[daytime[active]] = rng.uniform(100, 800, int(active.sum()))
    counts += rng.poisson(1.0, 1440)                           # fidget noise
    return counts
