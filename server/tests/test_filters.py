import numpy as np
import pandas as pd

from app.constants import CLEAN_SPEC
from app.processing.filters import (clean_stream, contiguous_segments, hampel,
                                    lowpass)


def _series(n=240, seed=7, freq="1min"):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-07-01", periods=n, freq=freq, tz="UTC")
    values = 60 + 5 * np.sin(np.linspace(0, 6, n)) + rng.normal(0, 1.0, n)
    return pd.Series(values, index=idx)


def test_hampel_removes_planted_spike():
    s = _series()
    spiked = s.copy()
    spiked.iloc[100] += 40.0
    spiked.iloc[180] -= 40.0
    cleaned, n_replaced = hampel(spiked)
    assert n_replaced >= 2
    assert abs(cleaned.iloc[100] - s.iloc[100]) < 5.0
    assert abs(cleaned.iloc[180] - s.iloc[180]) < 5.0


def test_lowpass_reduces_variance():
    s = _series(seed=11)
    filtered = lowpass(s.to_numpy(), cutoff_minutes=30.0)
    assert np.var(filtered) < np.var(s.to_numpy())


def test_lowpass_short_segment_passthrough():
    values = np.arange(20, dtype=float)
    assert np.array_equal(lowpass(values, 30.0), values)


def test_contiguous_segments_split_on_gap():
    a = pd.date_range("2026-07-01T00:00:00Z", periods=60, freq="1min")
    b = pd.date_range("2026-07-01T01:30:00Z", periods=60, freq="1min")  # 30-min hole
    idx = a.append(b)
    segments = contiguous_segments(idx)
    assert len(segments) == 2
    assert segments[0] == slice(0, 60)
    assert segments[1] == slice(60, 120)


def test_clean_stream_two_hours_max_120_bins():
    s = _series(n=240, freq="30s")  # 2 hours at 30-second cadence
    cleaned = clean_stream(s, CLEAN_SPEC["heart_rate"])
    assert len(cleaned) <= 120
    assert cleaned.index.tz is not None


def test_clean_stream_motion_sums_and_never_smooths():
    idx = pd.date_range("2026-07-01T10:00:00Z", periods=4, freq="30s")
    s = pd.Series([100.0, 200.0, 50.0, 25.0], index=idx)
    cleaned = clean_stream(s, CLEAN_SPEC["motion"])
    assert cleaned.iloc[0] == 300.0  # two 30s readings summed into the minute bin
    assert cleaned.iloc[1] == 75.0


def test_clean_stream_motion_gap_yields_no_fabricated_zero_bins():
    # A 30-min dropout must produce NO bins, not thirty fabricated 0.0 rows —
    # zero-filled gaps would defeat the min_bins partial-day guard downstream.
    a = pd.date_range("2026-07-01T10:00:00Z", periods=10, freq="1min")
    b = pd.date_range("2026-07-01T10:40:00Z", periods=10, freq="1min")
    s = pd.Series([50.0] * 20, index=a.append(b))
    cleaned = clean_stream(s, CLEAN_SPEC["motion"])
    assert len(cleaned) == 20
    assert (cleaned > 0).all()
