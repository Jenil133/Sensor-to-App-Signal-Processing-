# metric name -> (min, max); values outside are dropped (sensor glitch), not clamped,
# because a clamped fake value would poison baselines later.
STREAM_BOUNDS: dict[str, tuple[float, float]] = {
    "heart_rate": (25.0, 220.0),   # bpm
    "hrv_rmssd":  (5.0, 250.0),    # ms
    "skin_temp":  (30.0, 42.0),    # °C
    "motion":     (0.0, 100000.0), # activity counts per interval
}
MAX_BATCH_SAMPLES = 5000

# Per-stream cleaning spec: which filters apply and how 1-min bins are formed.
CLEAN_SPEC = {
    "heart_rate": {"hampel": True,  "lowpass_min": 30.0, "resample": "mean"},
    "skin_temp":  {"hampel": True,  "lowpass_min": 60.0, "resample": "mean"},
    "hrv_rmssd":  {"hampel": True,  "lowpass_min": None, "resample": "mean"},  # sparse; median-clean only
    "motion":     {"hampel": False, "lowpass_min": None, "resample": "sum"},   # counts: never smooth
}
# Derived daily metrics: (source stream, UTC hour window [start,end), min bins required, day agg)
DERIVED_METRICS = {
    "resting_hr":      ("heart_rate", (2, 5),  60, "mean"),
    "hrv_night":       ("hrv_rmssd",  (0, 6),  12, "mean"),
    "skin_temp_night": ("skin_temp",  (0, 6),  36, "mean"),
    "motion_total":    ("motion",     (0, 24), 60, "sum"),
}
BASELINE_WINDOW_DAYS = 14
BASELINE_MIN_DAYS = 7          # need ≥7 prior daily values before judging a day
MIN_SPREAD = {"resting_hr": 1.0, "hrv_night": 3.0, "skin_temp_night": 0.10, "motion_total": 500.0}
ZSCORE_MED, ZSCORE_HIGH = 3.0, 4.0
CUSUM_K, CUSUM_H = 0.5, 5.0
ISOFOREST_MIN_DAYS, ISOFOREST_TRAIN_DAYS = 21, 90
PIPELINE_REPROCESS_DAYS = 35   # idempotent trailing recompute window
