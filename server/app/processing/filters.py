import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt


def hampel(s: pd.Series, window: int = 11, k: float = 3.0) -> tuple[pd.Series, int]:
    """Replace isolated spikes with the rolling median (robust to the spike itself)."""
    med = s.rolling(window, center=True, min_periods=1).median()
    mad = (s - med).abs().rolling(window, center=True, min_periods=1).median()
    out = (s - med).abs() > (k * 1.4826 * mad).clip(lower=1e-9)
    return s.mask(out, med), int(out.sum())


def lowpass(values: np.ndarray, cutoff_minutes: float) -> np.ndarray:
    """Zero-phase Butterworth on a 1-min-sampled contiguous segment.
    fs = 1/60 Hz, Nyquist = 1/120 Hz, fc = 1/(60*cutoff_minutes) Hz
    => normalized Wn = fc / Nyquist = 2 / cutoff_minutes."""
    if len(values) < 30:                 # filtfilt needs len > padlen (=12 for order 3)
        return values
    b, a = butter(3, 2.0 / cutoff_minutes)
    return filtfilt(b, a, values)


def contiguous_segments(idx: pd.DatetimeIndex, max_gap_min: int = 5) -> list[slice]:
    """Split a 1-min index wherever the gap exceeds max_gap_min (never filter across gaps)."""
    if len(idx) == 0:
        return []
    gaps = np.flatnonzero(np.diff(idx.values).astype("timedelta64[m]").astype(int) > max_gap_min)
    bounds = [0, *(gaps + 1), len(idx)]
    return [slice(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]


def clean_stream(raw: pd.Series, spec: dict) -> pd.Series:
    """raw: tz-aware UTC DatetimeIndex -> cleaned 1-min series per CLEAN_SPEC."""
    s = raw.sort_index()
    s = s[~s.index.duplicated(keep="last")]
    if spec["hampel"]:
        s, _ = hampel(s)
    # min_count=1 keeps empty bins NaN (pandas default sum() zero-fills them,
    # which would fabricate "no activity" rows across gaps and defeat the
    # min_bins partial-day guard downstream)
    binned = (s.resample("1min").sum(min_count=1) if spec["resample"] == "sum"
              else s.resample("1min").mean())
    binned = binned.dropna()
    if spec["lowpass_min"]:
        vals = binned.to_numpy(copy=True)
        for seg in contiguous_segments(binned.index):
            vals[seg] = lowpass(vals[seg], spec["lowpass_min"])
        binned = pd.Series(vals, index=binned.index)
    return binned
