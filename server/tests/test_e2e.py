"""Full product slice on SQLite, autoencoder flag off (no torch needed):
register -> device -> 16 crafted days -> pipeline -> daily/z -> events -> ack
-> idempotent re-run."""
from datetime import date, datetime, timedelta, timezone

import pytest

TOTAL_DAYS = 16
SHIFT_DAYS = 3
HR_BASE, HRV_BASE, TEMP_BASE, MOTION_BASE = 60.0, 50.0, 33.5, 100.0
HR_SHIFT, TEMP_SHIFT = 8.0, 0.8   # +8 x MIN_SPREAD on resting_hr / skin_temp_night


def day_batch(day: date, shifted: bool):
    samples = []
    base = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)

    def iso(minute_offset, hour):
        return (base + timedelta(hours=hour, minutes=minute_offset)
                ).strftime("%Y-%m-%dT%H:%M:%SZ")

    hr = HR_BASE + (HR_SHIFT if shifted else 0.0)
    temp = TEMP_BASE + (TEMP_SHIFT if shifted else 0.0)
    for m in range(60):
        samples.append({"metric": "heart_rate", "ts": iso(m, 2), "value": hr})
    for m in range(12):
        samples.append({"metric": "hrv_rmssd", "ts": iso(m * 5, 0), "value": HRV_BASE})
    for m in range(36):
        samples.append({"metric": "skin_temp", "ts": iso(m, 1), "value": temp})
    for m in range(60):
        samples.append({"metric": "motion", "ts": iso(m, 12), "value": MOTION_BASE})
    return {"device_time": iso(0, 6), "samples": samples}


@pytest.mark.slow
def test_end_to_end_product_slice(client):
    # -- register / login / device
    assert client.post("/api/v1/auth/register",
                       json={"email": "e2e@example.com",
                             "password": "password123"}).status_code == 201
    token = client.post("/api/v1/auth/login",
                        json={"email": "e2e@example.com",
                              "password": "password123"}).json()["access_token"]
    headers = {"authorization": f"Bearer {token}"}
    device = client.post("/api/v1/devices", headers=headers,
                         json={"name": "E2E Watch"}).json()
    dev_headers = {"X-Device-Token": device["device_token"]}

    # -- 16 days of telemetry, last 3 shifted
    today = datetime.now(timezone.utc).date()
    days = [today - timedelta(days=TOTAL_DAYS - i) for i in range(TOTAL_DAYS)]
    for i, day in enumerate(days):
        resp = client.post("/api/v1/ingest", headers=dev_headers,
                           json=day_batch(day, i >= TOTAL_DAYS - SHIFT_DAYS))
        assert resp.status_code == 202, resp.text

    # -- pipeline
    run = client.post("/api/v1/pipeline/run", headers=headers).json()
    assert run["daily_rows"] > 0

    # -- daily series: z appears from ~day 8, shifted days breach
    rows = client.get("/api/v1/daily", params={"metric": "resting_hr"},
                      headers=headers).json()
    assert len(rows) == TOTAL_DAYS
    assert rows[0]["z"] is None
    assert all(r["z"] is not None for r in rows[8:])
    assert all(r["z"] >= 6.0 for r in rows[-SHIFT_DAYS:])

    # -- events fired
    events = client.get("/api/v1/anomalies", headers=headers).json()
    assert len(events) >= 1
    assert {e["detector"] for e in events} & {"zscore", "cusum"}

    # -- ack persists
    target = events[0]
    assert client.post(f"/api/v1/anomalies/{target['id']}/ack",
                       headers=headers).status_code == 200

    # -- idempotency: re-run changes nothing, ack survives, no reopen
    rerun = client.post("/api/v1/pipeline/run", headers=headers).json()
    assert rerun["clean_rows"] == run["clean_rows"]
    assert rerun["daily_rows"] == run["daily_rows"]
    assert rerun["events_created"] == 0
    after = client.get("/api/v1/anomalies", headers=headers).json()
    acked = [e for e in after if e["id"] == target["id"]]
    assert acked and acked[0]["status"] == "acked"
    assert len(after) == len(events)


def test_models_train_disabled_by_flag(client):
    client.post("/api/v1/auth/register",
                json={"email": "flag@example.com", "password": "password123"})
    token = client.post("/api/v1/auth/login",
                        json={"email": "flag@example.com",
                              "password": "password123"}).json()["access_token"]
    resp = client.post("/api/v1/models/train",
                       headers={"authorization": f"Bearer {token}"})
    assert resp.status_code == 409
    assert resp.json()["detail"] == "autoencoder disabled"


def test_security_headers_on_every_response(client):
    resp = client.get("/api/v1/health")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "no-referrer"
    assert resp.headers["Cache-Control"] == "no-store"
