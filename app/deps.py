from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import AuthUnavailableError, decode_access_token

bearer = HTTPBearer(auto_error=False)

Db = Annotated[Session, Depends(get_db)]


def sync_user(db: Session, claims: dict) -> User:
    """Supabase owns accounts; this keeps a local row per user for foreign keys and profile data."""
    metadata = claims.get("user_metadata") or {}
    email = (claims.get("email") or "").lower()
    name = (metadata.get("full_name") or metadata.get("name") or email).strip()[:200]

    user = db.get(User, claims["sub"])
    if user is None:
        user = User(id=claims["sub"], email=email, name=name)
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            user = db.get_one(User, claims["sub"])
    elif (user.email, user.name) != (email, name):
        user.email, user.name = email, name
        db.commit()
    return user


def get_current_user(
    db: Db,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    try:
        claims = decode_access_token(credentials.credentials) if credentials else None
    except AuthUnavailableError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication service is unreachable"
        ) from None
    if claims is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return sync_user(db, claims)


CurrentUser = Annotated[User, Depends(get_current_user)]
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]


def get_owned[T](db: Session, model: type[T], item_id: str, user: User) -> T:
    item = db.get(model, item_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{model.__name__} not found")
    return item
