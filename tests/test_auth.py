from datetime import UTC, datetime, timedelta

import jwt
from cryptography.hazmat.primitives.asymmetric import ec

from app import security
from tests.conftest import supabase_token, user_headers


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_me_creates_a_profile_from_the_supabase_token(client):
    token = supabase_token("Ada@Example.com", user_id="11111111-1111-1111-1111-111111111111")
    me = client.get("/api/v1/auth/me", headers=bearer(token))
    assert me.status_code == 200
    assert me.json() == {
        "id": "11111111-1111-1111-1111-111111111111",
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "roles": ["member"],
    }


def test_profile_follows_changes_made_in_supabase(client):
    client.get("/api/v1/auth/me", headers=user_headers())
    renamed = client.get("/api/v1/auth/me", headers=user_headers(full_name="Ada King"))
    assert renamed.json()["name"] == "Ada King"


def test_name_falls_back_to_email(client):
    me = client.get("/api/v1/auth/me", headers=bearer(supabase_token(user_metadata={})))
    assert me.json()["name"] == "ada@example.com"


def test_missing_or_malformed_token_is_rejected(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers=bearer("nope")).status_code == 401


def test_token_signed_by_another_key_is_rejected(client):
    forged = supabase_token(key=ec.generate_private_key(ec.SECP256R1()))
    assert client.get("/api/v1/auth/me", headers=bearer(forged)).status_code == 401


def test_expired_token_is_rejected(client):
    expired = supabase_token(exp=datetime.now(UTC) - timedelta(minutes=1))
    assert client.get("/api/v1/auth/me", headers=bearer(expired)).status_code == 401


def test_token_for_another_audience_or_project_is_rejected(client):
    anon = supabase_token(aud="anon")
    other_project = supabase_token(iss="https://someone-else.supabase.co/auth/v1")
    assert client.get("/api/v1/auth/me", headers=bearer(anon)).status_code == 401
    assert client.get("/api/v1/auth/me", headers=bearer(other_project)).status_code == 401


def test_symmetric_tokens_are_rejected(client):
    hs256 = jwt.encode(
        {"sub": "x", "aud": "authenticated", "exp": datetime.now(UTC) + timedelta(hours=1)},
        "a-shared-secret-that-is-long-enough-for-hs256",
        algorithm="HS256",
    )
    assert client.get("/api/v1/auth/me", headers=bearer(hs256)).status_code == 401


def test_unreachable_jwks_is_a_503_not_a_401(client, monkeypatch):
    def unreachable(token):
        raise jwt.PyJWKClientConnectionError("down")

    monkeypatch.setattr(security, "get_signing_key", unreachable)
    assert client.get("/api/v1/auth/me", headers=user_headers()).status_code == 503
