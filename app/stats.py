from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import TelemetryEvent, TrainingSession


def target_stats(db: Session, *session_filters) -> dict:
    counts = dict(
        db.execute(
            select(TelemetryEvent.event_type, func.count())
            .select_from(TelemetryEvent)
            .join(TrainingSession)
            .where(
                *session_filters,
                TelemetryEvent.event_type.in_(["TARGET_SHOWN", "TARGET_REACHED", "TARGET_MISSED"]),
            )
            .group_by(TelemetryEvent.event_type)
        ).all()
    )
    average, fastest, slowest = db.execute(
        select(
            func.avg(TelemetryEvent.reaction_time_ms),
            func.min(TelemetryEvent.reaction_time_ms),
            func.max(TelemetryEvent.reaction_time_ms),
        )
        .select_from(TelemetryEvent)
        .join(TrainingSession)
        .where(*session_filters, TelemetryEvent.event_type == "TARGET_REACHED")
    ).one()

    completed = counts.get("TARGET_REACHED", 0)
    missed = counts.get("TARGET_MISSED", 0)
    return {
        # Real Pi firmware doesn't announce every target, so never report fewer than were resolved.
        "targets_attempted": max(counts.get("TARGET_SHOWN", 0), completed + missed),
        "targets_completed": completed,
        "targets_missed": missed,
        "average_target_time_ms": average,
        "fastest_target_time_ms": fastest,
        "slowest_target_time_ms": slowest,
    }
