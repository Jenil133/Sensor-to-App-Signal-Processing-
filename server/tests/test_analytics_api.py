"""Full analytics slice on SQLite: crafted days -> pipeline -> daily/z -> events -> ack."""
from datetime import date, datetime, timedelta, timezone

SHIFT_DAYS = 3          # last N days carry the physiological shift
TOTAL_DAYS = 12
HR_BASE, HRV_BASE, TEMP_BASE, MOTION_BASE = 60.0, 50.0, 33.5, 100.0
HR_SHIFT, TEMP_SHIFT = 8.0, 0.8    # +8 x MIN_SPREAD each


def day_batch(day: date, shifted: bool):
    """Compact synthetic day hitting every DERIVED_METRICS window's min_bins."""
    samples = []
    base = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)

    def iso(minute_offset, hour):
        return (base + timedelta(hours=hour, minutes=minute_offset)
                ).strftime("%Y-%m-%dT%H:%M:%SZ")

    hr = HR_BASE + (HR_SHIFT if shifted else 0.0)
    temp = TEMP_BASE + (TEMP_SHIFT if shifted else 0.0)
    for m in range(60):     # resting_hr window 02-05, needs 60 bins
        samples.append({"metric": "heart_rate", "ts": iso(m, 2), "value": hr})
    for m in range(12):     # hrv_night window 00-06, needs 12 bins
        samples.append({"metric": "hrv_rmssd", "ts": iso(m * 5, 0), "value": HRV_BASE})
    for m in range(36):     # skin_temp_night window 00-06, needs 36 bins
        samples.append({"metric": "skin_temp", "ts": iso(m, 1), "value": temp})
    for m in range(60):     # motion_total whole day, needs 60 bins
        samples.append({"metric": "motion", "ts": iso(m, 12), "value": MOTION_BASE})
    return {"device_time": iso(0, 6), "samples": samples}


def setup_user(client):
    client.post("/api/v1/auth/register",
                json={"email": "analytics@example.com", "password": "password123"})
    token = client.post("/api/v1/auth/login",
                        json={"email": "analytics@example.com",
                              "password": "password123"}).json()["access_token"]
    headers = {"authorization": f"Bearer {token}"}
    device_token = client.post("/api/v1/devices", headers=headers,
                               json={"name": "Sim"}).json()["device_token"]
    return headers, {"X-Device-Token": device_token}


def ingest_days(client, dev_headers):
    today = datetime.now(timezone.utc).date()
    days = [today - timedelta(days=TOTAL_DAYS - i) for i in range(TOTAL_DAYS)]
    for i, day in enumerate(days):
        shifted = i >= TOTAL_DAYS - SHIFT_DAYS
        resp = client.post("/api/v1/ingest", headers=dev_headers,
                           json=day_batch(day, shifted))
        assert resp.status_code == 202, resp.text
    return days


def test_full_analytics_slice(client):
    headers, dev_headers = setup_user(client)
    days = ingest_days(client, dev_headers)

    run = client.post("/api/v1/pipeline/run", headers=headers)
    assert run.status_code == 200
    body = run.json()
    assert body["clean_rows"] > 0
    assert body["daily_rows"] >= TOTAL_DAYS  # at least all resting_hr days

    daily = client.get("/api/v1/daily", params={"metric": "resting_hr"},
                       headers=headers)
    assert daily.status_code == 200
    rows = daily.json()
    assert len(rows) == TOTAL_DAYS
    assert [r["day"] for r in rows] == [d.isoformat() for d in days]
    # first week: no baseline yet -> null z; later rows have z and bands
    assert rows[0]["z"] is None and rows[0]["baseline_center"] is None
    with_z = [r for r in rows if r["z"] is not None]
    assert len(with_z) >= SHIFT_DAYS + 1
    shifted_rows = rows[-SHIFT_DAYS:]
    for r in shifted_rows:
        assert r["z"] is not None and r["z"] >= 6.0   # +8 x MIN_SPREAD floor
        assert r["baseline_center"] is not None and r["baseline_spread"] is not None

    anomalies = client.get("/api/v1/anomalies", headers=headers)
    assert anomalies.status_code == 200
    events = anomalies.json()
    assert len(events) >= 1
    detectors = {e["detector"] for e in events}
    assert "zscore" in detectors or "cusum" in detectors
    metrics_hit = {e["metric"] for e in events}
    assert "resting_hr" in metrics_hit or "skin_temp_night" in metrics_hit

    # ack lifecycle
    target = events[0]
    ack = client.post(f"/api/v1/anomalies/{target['id']}/ack", headers=headers)
    assert ack.status_code == 200
    assert ack.json() == {"id": target["id"], "status": "acked"}

    # idempotency: re-run changes no counts on unchanged data, ack persists
    rerun = client.post("/api/v1/pipeline/run", headers=headers).json()
    assert rerun["clean_rows"] == body["clean_rows"]
    assert rerun["daily_rows"] == body["daily_rows"]
    assert rerun["events_created"] == 0
    after = client.get("/api/v1/anomalies", headers=headers,
                       params={"status": "acked"}).json()
    assert any(e["id"] == target["id"] for e in after)


def test_daily_unknown_metric_422(client):
    headers, _ = setup_user(client)
    assert client.get("/api/v1/daily", params={"metric": "heart_rate"},
                      headers=headers).status_code == 422


def test_anomalies_bad_status_422(client):
    headers, _ = setup_user(client)
    assert client.get("/api/v1/anomalies", params={"status": "weird"},
                      headers=headers).status_code == 422


def test_ack_foreign_anomaly_404(client):
    headers, _ = setup_user(client)
    assert client.post("/api/v1/anomalies/nonexistent-id/ack",
                       headers=headers).status_code == 404
