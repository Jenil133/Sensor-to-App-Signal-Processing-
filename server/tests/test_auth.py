EMAIL = "me@example.com"
PASSWORD = "password123"


def register(client, email=EMAIL, password=PASSWORD):
    return client.post("/api/v1/auth/register",
                       json={"email": email, "password": password})


def login(client, email=EMAIL, password=PASSWORD):
    return client.post("/api/v1/auth/login",
                       json={"email": email, "password": password})


def test_register_returns_201_with_user(client):
    resp = register(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == EMAIL
    assert body["id"]
    assert "password" not in body and "password_hash" not in body


def test_duplicate_email_returns_409(client):
    assert register(client).status_code == 201
    assert register(client).status_code == 409


def test_login_returns_token_and_me_matches(client):
    register(client)
    resp = login(client)
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    token = body["access_token"]
    me = client.get("/api/v1/me", headers={"authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == EMAIL


def test_bad_password_returns_401(client):
    register(client)
    assert login(client, password="wrong-password").status_code == 401


def test_me_without_token_rejected(client):
    resp = client.get("/api/v1/me", headers={"authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401


def test_register_multibyte_password_over_72_bytes_is_422(client):
    # 40 chars but 80 UTF-8 bytes — must be a validation error, not a bcrypt 500
    resp = register(client, password="ü" * 40)
    assert resp.status_code == 422


def test_login_oversized_password_is_401_not_500(client):
    # bcrypt >=5 raises past 72 bytes; login must stay a uniform 401
    # (a 500 only for registered emails would be a user-enumeration oracle)
    register(client)
    assert login(client, password="x" * 100).status_code == 401
