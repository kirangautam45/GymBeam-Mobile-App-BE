import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """SQLite drops tzinfo, so normalise to aware UTC on the way in and out."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class Base(DeclarativeBase):
    pass


class User(Base):
    """Mirror of a Supabase auth user; the id is the Supabase user id."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), index=True, default="")
    name: Mapped[str] = mapped_column(String(200), default="")
    roles: Mapped[list[str]] = mapped_column(JSON, default=lambda: ["member"])
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Pattern(Base):
    __tablename__ = "patterns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    targets: Mapped[list[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    pattern_id: Mapped[str] = mapped_column(ForeignKey("patterns.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(2000), default="")
    difficulty: Mapped[str] = mapped_column(String(20))
    estimated_duration_seconds: Mapped[int] = mapped_column(Integer)
    sets: Mapped[int] = mapped_column(Integer, default=1)
    rounds: Mapped[int] = mapped_column(Integer, default=1)
    rest_seconds: Mapped[int] = mapped_column(Integer, default=0)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_favorite: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    pattern: Mapped[Pattern] = relationship(lazy="joined")

    @property
    def target_count(self) -> int:
        return len(self.pattern.targets)


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (UniqueConstraint("user_id", "mac_address"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    mac_address: Mapped[str] = mapped_column(String(64))
    device_type: Mapped[str] = mapped_column(String(60), default="")
    manufacturer: Mapped[str] = mapped_column(String(120), default="")
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    metrics: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class TrainingSession(Base):
    __tablename__ = "sessions"
    __table_args__ = (Index("ix_sessions_user_started", "user_id", "started_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    exercise_id: Mapped[str | None] = mapped_column(
        ForeignKey("exercises.id", ondelete="SET NULL"), default=None
    )
    device_id: Mapped[str | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), default=None
    )
    name: Mapped[str] = mapped_column(String(120), default="")
    state: Mapped[str] = mapped_column(String(20), default="running")
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)


class TelemetryEvent(Base):
    __tablename__ = "telemetry_events"
    __table_args__ = (Index("ix_telemetry_session_type", "session_id", "event_type"),)

    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True
    )
    event_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    schema_version: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(40))
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime)
    device_timestamp: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    target_id: Mapped[str | None] = mapped_column(String(120), default=None)
    target_index: Mapped[int | None] = mapped_column(Integer, default=None)
    coordinates: Mapped[dict | None] = mapped_column(JSON, default=None)
    state: Mapped[str | None] = mapped_column(String(40), default=None)
    metrics: Mapped[dict | None] = mapped_column(JSON, default=None)
    reaction_time_ms: Mapped[float | None] = mapped_column(Float, default=None)
