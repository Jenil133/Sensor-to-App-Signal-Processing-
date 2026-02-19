from app.models import RawPayload

BASE_TS = "2026-07-01T00:{minute:02d}:00Z"


def make_user_device(client):
    client.post("/api/v1/auth/register",
                json={"email": "ingest@example.com", "password": "password123"})
    token = client.post("/api/v1/auth/login",
                        json={"email": "ingest@example.com",
                              "password": "password123"}).json()["access_token"]
    device = client.post("/api/v1/devices",
                         headers={"authorization": f"Bearer {token}"},
                         json={"name": "Sim Watch"})
    assert device.status_code == 201
    body = device.json()
    assert body["device_token"].startswith("bld_")
    return token, body["device_token"]


def batch(samples):
    return {"device_time": "2026-07-01T06:00:00Z", "samples": samples}


FIVE_SAMPLES = [
    {"metric": "heart_rate", "ts": BASE_TS.format(minute=0), "value": 61.0},
    {"metric": "heart_rate", "ts": BASE_TS.format(minute=1), "value": 62.5},
    {"metric": "hrv_rmssd", "ts": BASE_TS.format(minute=0), "value": 52.0},
    {"metric": "skin_temp", "ts": BASE_TS.format(minute=0), "value": 33.5},
    {"metric": "motion", "ts": BASE_TS.format(minute=0), "value": 12.0},
]


def test_full_ingest_slice(client, db_session):
    token, device_token = make_user_device(client)
    headers = {"X-Device-Token": device_token}

    # ingest 5 samples
    resp = client.post("/api/v1/ingest", headers=headers, json=batch(FIVE_SAMPLES))
    assert resp.status_code == 202
    body = resp.json()
    assert body["stored"] == 5
    assert body["dropped_out_of_range"] == 0
    assert body["dropped_duplicates"] == 0

    # identical resend: everything deduped
    resp = client.post("/api/v1/ingest", headers=headers, json=batch(FIVE_SAMPLES))
    assert resp.status_code == 202
    body = resp.json()
    assert body["stored"] == 0
    assert body["dropped_duplicates"] == 5

    # out-of-range value dropped, not clamped
    resp = client.post("/api/v1/ingest", headers=headers, json=batch(
        [{"metric": "heart_rate", "ts": BASE_TS.format(minute=2), "value": 300.0}]))
    assert resp.status_code == 202
    body = resp.json()
    assert body["stored"] == 0
    assert body["dropped_out_of_range"] == 1

    # read back ordered heart-rate points
    resp = client.get(
        "/api/v1/metrics",
        params={"metric": "heart_rate", "start": "2026-07-01T00:00:00Z",
                "end": "2026-07-01T01:00:00Z"},
        headers={"authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    points = resp.json()
    assert [p["value"] for p in points] == [61.0, 62.5]
    assert points == sorted(points, key=lambda p: p["ts"])

    # at-rest encryption: plaintext metric name must not be greppable in the blob
    payloads = db_session.query(RawPayload).all()
    assert len(payloads) == 3
    for p in payloads:
        assert b"heart_rate" not in p.ciphertext
        assert p.sha256
    assert payloads[0].processed is True
    assert payloads[0].sample_count == 5


def test_unknown_metric_rejected(client):
    _, device_token = make_user_device(client)
    resp = client.post("/api/v1/ingest", headers={"X-Device-Token": device_token},
                       json=batch([{"metric": "steps", "ts": BASE_TS.format(minute=0),
                                    "value": 10.0}]))
    assert resp.status_code == 422


def test_naive_timestamp_rejected(client):
    _, device_token = make_user_device(client)
    resp = client.post("/api/v1/ingest", headers={"X-Device-Token": device_token},
                       json=batch([{"metric": "heart_rate",
                                    "ts": "2026-07-01T00:00:00", "value": 60.0}]))
    assert resp.status_code == 422


def test_bad_device_token_rejected(client):
    make_user_device(client)
    resp = client.post("/api/v1/ingest", headers={"X-Device-Token": "bld_wrong"},
                       json=batch(FIVE_SAMPLES))
    assert resp.status_code == 401


def test_missing_device_token_header_is_401(client):
    make_user_device(client)
    assert client.post("/api/v1/ingest", json=batch(FIVE_SAMPLES)).status_code == 401


def test_dedupe_across_timezone_offsets(client):
    # Same instant sent with a +05:30 offset must dedupe against the stored UTC row
    _, device_token = make_user_device(client)
    headers = {"X-Device-Token": device_token}
    utc = client.post("/api/v1/ingest", headers=headers, json=batch(
        [{"metric": "heart_rate", "ts": "2026-07-01T00:00:00Z", "value": 61.0}]))
    assert utc.json()["stored"] == 1
    offset = client.post("/api/v1/ingest", headers=headers, json=batch(
        [{"metric": "heart_rate", "ts": "2026-07-01T05:30:00+05:30", "value": 61.0}]))
    body = offset.json()
    assert body["stored"] == 0
    assert body["dropped_duplicates"] == 1
