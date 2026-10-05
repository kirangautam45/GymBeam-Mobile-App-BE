import os
import uuid
from datetime import UTC, datetime, timedelta

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SUPABASE_URL"] = "https://test-project.supabase.co"
os.environ["SUPABASE_JWKS_URL"] = ""

import jwt  # noqa: E402
import pytest  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import security  # noqa: E402
from app.db import build_engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402

ISSUER = "https://test-project.supabase.co/auth/v1"
SIGNING_KEY = ec.generate_private_key(ec.SECP256R1())


def supabase_token(
    email="ada@example.com",
    full_name="Ada Lovelace",
    user_id=None,
    key=SIGNING_KEY,
    **claim_overrides,
):
    """Builds an access token shaped like the ones Supabase Auth issues."""
    now = datetime.now(UTC)
    claims = {
        "iss": ISSUER,
        "aud": "authenticated",
        "sub": user_id or str(uuid.uuid5(uuid.NAMESPACE_DNS, email)),
        "email": email,
        "role": "authenticated",
        "user_metadata": {"full_name": full_name},
        "iat": now,
        "exp": now + timedelta(hours=1),
        **claim_overrides,
    }
    return jwt.encode(claims, key, algorithm="ES256", headers={"kid": "test-key"})


def user_headers(email="ada@example.com", **kwargs):
    return {"Authorization": f"Bearer {supabase_token(email, **kwargs)}"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(security, "get_signing_key", lambda token: SIGNING_KEY.public_key())

    engine = build_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(engine, expire_on_commit=False)

    def override_get_db():
        with TestSession() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def headers():
    return user_headers()
