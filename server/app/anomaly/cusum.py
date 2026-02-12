def cusum_alarms(z: list[float], k: float = 0.5, h: float = 5.0) -> list[dict]:
    """Two-sided CUSUM on standardized daily residuals.
    Accumulates small persistent deviations — the right tool for *subtle sustained shifts*
    that never individually cross a z threshold. Resets after each alarm."""
    s_pos = s_neg = 0.0
    alarms, start_pos, start_neg = [], 0, 0
    for i, val in enumerate(z):
        s_pos = max(0.0, s_pos + val - k)
        s_neg = max(0.0, s_neg - val - k)
        if s_pos == 0.0:
            start_pos = i + 1
        if s_neg == 0.0:
            start_neg = i + 1
        if s_pos > h or s_neg > h:
            up = s_pos > h
            alarms.append({"index": i, "direction": "+" if up else "-",
                           "statistic": round(max(s_pos, s_neg), 2),
                           "onset_index": start_pos if up else start_neg})
            s_pos = s_neg = 0.0
            start_pos = start_neg = i + 1
    return alarms
