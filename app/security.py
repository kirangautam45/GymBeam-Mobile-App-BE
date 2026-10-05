from functools import lru_cache

import jwt

from app.config import get_settings

ALGORITHMS = ["ES256", "RS256"]


class AuthUnavailableError(Exception):
    pass


@lru_cache
def jwks_client() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(get_settings().jwks_url, cache_keys=True, lifespan=3600)


def get_signing_key(token: str):
    return jwks_client().get_signing_key_from_jwt(token).key


def decode_access_token(token: str) -> dict | None:
    """Returns the claims of a Supabase-issued access token, or None if it isn't valid."""
    try:
        return jwt.decode(
            token,
            get_signing_key(token),
            algorithms=ALGORITHMS,
            audience="authenticated",
            issuer=get_settings().supabase_issuer,
            options={"require": ["sub", "exp"]},
        )
    except jwt.PyJWKClientConnectionError as error:
        raise AuthUnavailableError from error
    except jwt.PyJWTError:
        return None
