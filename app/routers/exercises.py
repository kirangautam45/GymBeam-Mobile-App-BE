from fastapi import APIRouter, status
from sqlalchemy import select

from app.deps import CurrentUser, Db, Limit, Offset, get_owned
from app.models import Exercise, Pattern
from app.schemas import ExerciseIn, ExerciseOut, ExerciseUpdate

router = APIRouter(prefix="/exercises", tags=["exercises"])


@router.get("", response_model=list[ExerciseOut])
def list_exercises(
    db: Db,
    user: CurrentUser,
    favorite: bool | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
):
    query = select(Exercise).where(Exercise.user_id == user.id)
    if favorite is not None:
        query = query.where(Exercise.is_favorite == favorite)
    return db.scalars(query.order_by(Exercise.updated_at.desc()).limit(limit).offset(offset)).all()


@router.post("", response_model=ExerciseOut, status_code=status.HTTP_201_CREATED)
def create_exercise(body: ExerciseIn, db: Db, user: CurrentUser):
    get_owned(db, Pattern, body.pattern_id, user)
    exercise = Exercise(user_id=user.id, **body.model_dump())
    db.add(exercise)
    db.commit()
    return exercise


@router.get("/{exercise_id}", response_model=ExerciseOut)
def get_exercise(exercise_id: str, db: Db, user: CurrentUser):
    return get_owned(db, Exercise, exercise_id, user)


@router.patch("/{exercise_id}", response_model=ExerciseOut)
def update_exercise(exercise_id: str, body: ExerciseUpdate, db: Db, user: CurrentUser):
    exercise = get_owned(db, Exercise, exercise_id, user)
    changes = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if "pattern_id" in changes:
        get_owned(db, Pattern, changes["pattern_id"], user)
    for field, value in changes.items():
        setattr(exercise, field, value)
    db.commit()
    db.refresh(exercise)
    return exercise


@router.delete("/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exercise(exercise_id: str, db: Db, user: CurrentUser):
    db.delete(get_owned(db, Exercise, exercise_id, user))
    db.commit()
