from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.deps import CurrentUser, Db, Limit, Offset, get_owned
from app.models import Exercise, Pattern
from app.schemas import PatternIn, PatternOut

router = APIRouter(prefix="/patterns", tags=["patterns"])


@router.get("", response_model=list[PatternOut])
def list_patterns(db: Db, user: CurrentUser, limit: Limit = 50, offset: Offset = 0):
    return db.scalars(
        select(Pattern)
        .where(Pattern.user_id == user.id)
        .order_by(Pattern.updated_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()


@router.post("", response_model=PatternOut, status_code=status.HTTP_201_CREATED)
def create_pattern(body: PatternIn, db: Db, user: CurrentUser):
    pattern = Pattern(user_id=user.id, **body.model_dump())
    db.add(pattern)
    db.commit()
    return pattern


@router.get("/{pattern_id}", response_model=PatternOut)
def get_pattern(pattern_id: str, db: Db, user: CurrentUser):
    return get_owned(db, Pattern, pattern_id, user)


@router.put("/{pattern_id}", response_model=PatternOut)
def update_pattern(pattern_id: str, body: PatternIn, db: Db, user: CurrentUser):
    pattern = get_owned(db, Pattern, pattern_id, user)
    pattern.name = body.name
    pattern.targets = [target.model_dump() for target in body.targets]
    db.commit()
    return pattern


@router.delete("/{pattern_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pattern(pattern_id: str, db: Db, user: CurrentUser):
    pattern = get_owned(db, Pattern, pattern_id, user)
    in_use = db.scalar(select(func.count()).where(Exercise.pattern_id == pattern.id))
    if in_use:
        raise HTTPException(status.HTTP_409_CONFLICT, "Pattern is used by one or more exercises")
    db.delete(pattern)
    db.commit()
