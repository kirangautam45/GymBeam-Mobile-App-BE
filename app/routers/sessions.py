from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.deps import CurrentUser, Db, Limit, Offset, get_owned
from app.models import Device, Exercise, TelemetryEvent, TrainingSession, utcnow
from app.schemas import (
    IngestResult,
    SessionIn,
    SessionMetrics,
    SessionOut,
    TelemetryEventIn,
    TelemetryEventOut,
)
from app.stats import target_stats

router = APIRouter(prefix="/sessions", tags=["sessions"])

STATE_AFTER_EVENT = {
    "SESSION_STARTED": "running",
    "SESSION_COMPLETED": "completed",
    "SESSION_STOPPED": "stopped",
    "ERROR": "error",
}


@router.get("", response_model=list[SessionOut])
def list_sessions(db: Db, user: CurrentUser, limit: Limit = 50, offset: Offset = 0):
    return db.scalars(
        select(TrainingSession)
        .where(TrainingSession.user_id == user.id)
        .order_by(TrainingSession.started_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def create_session(body: SessionIn, db: Db, user: CurrentUser):
    if body.exercise_id:
        get_owned(db, Exercise, body.exercise_id, user)
    if body.device_id:
        get_owned(db, Device, body.device_id, user)
    session = TrainingSession(
        user_id=user.id,
        name=body.name,
        exercise_id=body.exercise_id,
        device_id=body.device_id,
        started_at=body.started_at or utcnow(),
    )
    db.add(session)
    db.commit()
    return session


@router.get("/{session_id}", response_model=SessionOut)
def get_session(session_id: str, db: Db, user: CurrentUser):
    return get_owned(db, TrainingSession, session_id, user)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str, db: Db, user: CurrentUser):
    db.delete(get_owned(db, TrainingSession, session_id, user))
    db.commit()


@router.post("/{session_id}/events", response_model=IngestResult)
def ingest_events(
    session_id: str,
    events: Annotated[list[TelemetryEventIn], Body(min_length=1, max_length=500)],
    db: Db,
    user: CurrentUser,
):
    """Accepts a batch of telemetry events. Safe to retry: known event ids are skipped."""
    session = get_owned(db, TrainingSession, session_id, user)
    seen = set(
        db.scalars(
            select(TelemetryEvent.event_id).where(
                TelemetryEvent.session_id == session.id,
                TelemetryEvent.event_id.in_([event.event_id for event in events]),
            )
        )
    )

    accepted = 0
    for event in sorted(events, key=lambda e: e.timestamp):
        if event.event_id in seen:
            continue
        seen.add(event.event_id)
        accepted += 1
        db.add(
            TelemetryEvent(
                session_id=session.id,
                reaction_time_ms=(event.metrics or {}).get("reactionTimeMs"),
                **event.model_dump(exclude={"session_id"}),
            )
        )
        next_state = STATE_AFTER_EVENT.get(event.event_type)
        if next_state:
            session.state = next_state
            session.completed_at = None if next_state == "running" else event.timestamp

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Events were written concurrently, retry the batch"
        ) from None
    return IngestResult(accepted=accepted, duplicates=len(events) - accepted, state=session.state)


@router.get("/{session_id}/events", response_model=list[TelemetryEventOut])
def list_events(session_id: str, db: Db, user: CurrentUser, limit: Limit = 200, offset: Offset = 0):
    session = get_owned(db, TrainingSession, session_id, user)
    return db.scalars(
        select(TelemetryEvent)
        .where(TelemetryEvent.session_id == session.id)
        .order_by(TelemetryEvent.timestamp, TelemetryEvent.event_id)
        .limit(limit)
        .offset(offset)
    ).all()


@router.get("/{session_id}/metrics", response_model=SessionMetrics)
def get_metrics(session_id: str, db: Db, user: CurrentUser):
    session = get_owned(db, TrainingSession, session_id, user)
    return SessionMetrics(
        session_id=session.id,
        exercise_id=session.exercise_id,
        started_at=session.started_at,
        completed_at=session.completed_at,
        **target_stats(db, TrainingSession.id == session.id),
    )
