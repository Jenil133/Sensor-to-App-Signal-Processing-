# metric name -> (min, max); values outside are dropped (sensor glitch), not clamped,
# because a clamped fake value would poison baselines later.
STREAM_BOUNDS: dict[str, tuple[float, float]] = {
    "heart_rate": (25.0, 220.0),   # bpm
    "hrv_rmssd":  (5.0, 250.0),    # ms
    "skin_temp":  (30.0, 42.0),    # °C
    "motion":     (0.0, 100000.0), # activity counts per interval
}
MAX_BATCH_SAMPLES = 5000
