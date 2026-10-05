from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.deps import CurrentUser, Db
from app.models import TrainingSession
from app.schemas import AnalyticsSummary
from app.stats import target_stats

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
def summary(
    db: Db,
    user: CurrentUser,
    start: Annotated[datetime | None, Query(alias="from")] = None,
    end: Annotated[datetime | None, Query(alias="to")] = None,
):
    filters = [TrainingSession.user_id == user.id]
    if start:
        filters.append(TrainingSession.started_at >= start)
    if end:
        filters.append(TrainingSession.started_at < end)

    sessions = db.execute(
        select(
            TrainingSession.state, TrainingSession.started_at, TrainingSession.completed_at
        ).where(*filters)
    ).all()
    stats = target_stats(db, *filters)
    resolved = stats["targets_completed"] + stats["targets_missed"]

    return AnalyticsSummary(
        total_sessions=len(sessions),
        completed_sessions=sum(1 for s in sessions if s.state == "completed"),
        total_active_seconds=sum(
            max((s.completed_at - s.started_at).total_seconds(), 0)
            for s in sessions
            if s.completed_at
        ),
        accuracy_percent=round(stats["targets_completed"] / resolved * 100, 1)
        if resolved
        else None,
        **stats,
    )
