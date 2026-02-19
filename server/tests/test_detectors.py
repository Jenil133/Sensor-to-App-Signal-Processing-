import numpy as np
import pandas as pd

from app.anomaly.cusum import cusum_alarms
from app.anomaly.isoforest import isoforest_flags


def test_cusum_fires_once_in_shifted_region():
    rng = np.random.default_rng(0)
    z = list(rng.normal(0, 1, 20)) + list(rng.normal(1.2, 1, 10))
    alarms = cusum_alarms(z, k=0.5, h=5.0)
    assert len(alarms) == 1
    alarm = alarms[0]
    assert alarm["direction"] == "+"
    assert alarm["index"] >= 20          # fires inside the shifted region
    assert alarm["onset_index"] >= 15    # onset attributed near the shift start
    assert alarm["statistic"] > 5.0


def test_cusum_quiet_on_noise():
    rng = np.random.default_rng(1)
    assert cusum_alarms(list(rng.normal(0, 1, 40))) == []


def test_isoforest_flags_planted_outliers():
    rng = np.random.default_rng(0)
    days = pd.date_range("2026-06-01", periods=40, freq="D").date
    df = pd.DataFrame(rng.normal(0, 1, (40, 4)), index=days,
                      columns=["resting_hr", "hrv_night", "skin_temp_night", "motion_total"])
    df.iloc[30] = [4.2, -3.8, 4.0, 3.9]
    df.iloc [35] = [3.9, -4.1, 4.3, 4.0]
    flags = isoforest_flags(df)
    flagged_days = {f["day"] for f in flags}
    assert days[30] in flagged_days
    assert days[35] in flagged_days
    for f in flags:
        if f["day"] in (days[30], days[35]):
            assert f["top_feature"] in df.columns


def test_isoforest_insufficient_history_returns_empty():
    rng = np.random.default_rng(2)
    days = pd.date_range("2026-06-01", periods=10, freq="D").date
    df = pd.DataFrame(rng.normal(0, 1, (10, 4)), index=days,
                      columns=["resting_hr", "hrv_night", "skin_temp_night", "motion_total"])
    assert isoforest_flags(df) == []


def test_isoforest_nan_rows_dropped_not_imputed():
    rng = np.random.default_rng(3)
    days = pd.date_range("2026-06-01", periods=25, freq="D").date
    df = pd.DataFrame(rng.normal(0, 1, (25, 4)), index=days,
                      columns=["resting_hr", "hrv_night", "skin_temp_night", "motion_total"])
    df.iloc[5, 0] = np.nan
    df.iloc[6, 1] = np.nan
    df.iloc[7, 2] = np.nan
    df.iloc[8, 3] = np.nan
    df.iloc[9, 0] = np.nan
    # 20 complete rows < ISOFOREST_MIN_DAYS -> empty, proving NaN rows dropped
    assert isoforest_flags(df) == []
