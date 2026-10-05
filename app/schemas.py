from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

Difficulty = Literal["beginner", "intermediate", "advanced"]
SessionStatus = Literal["running", "completed", "stopped", "error"]
TelemetryEventType = Literal[
    "SESSION_STARTED",
    "SESSION_STOPPED",
    "SESSION_COMPLETED",
    "SET_STARTED",
    "SET_COMPLETED",
    "ROUND_STARTED",
    "ROUND_COMPLETED",
    "TARGET_SHOWN",
    "TARGET_REACHED",
    "TARGET_MISSED",
    "TARGET_CHANGED",
    "PAUSED",
    "RESUMED",
    "ERROR",
    "DEVICE_CONNECTED",
    "DEVICE_DISCONNECTED",
]


class CamelModel(BaseModel):
    """JSON is camelCase on the wire to match the mobile app's TypeScript types."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class UserOut(CamelModel):
    id: str
    name: str
    email: str
    roles: list[str]


class TargetPoint(CamelModel):
    x: float = Field(ge=-10, le=10)
    y: float = Field(ge=-10, le=10)


class PatternIn(CamelModel):
    name: str = Field(min_length=1, max_length=120)
    targets: list[TargetPoint] = Field(min_length=1, max_length=100)


class PatternOut(CamelModel):
    id: str
    name: str
    targets: list[TargetPoint]
    created_at: datetime
    updated_at: datetime


class ExerciseIn(CamelModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    difficulty: Difficulty
    estimated_duration_seconds: int = Field(ge=0)
    sets: int = Field(default=1, ge=1)
    rounds: int = Field(default=1, ge=1)
    rest_seconds: int = Field(default=0, ge=0)
    pattern_id: str
    tags: list[str] = Field(default_factory=list, max_length=20)
    is_favorite: bool = False


class ExerciseUpdate(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    difficulty: Difficulty | None = None
    estimated_duration_seconds: int | None = Field(default=None, ge=0)
    sets: int | None = Field(default=None, ge=1)
    rounds: int | None = Field(default=None, ge=1)
    rest_seconds: int | None = Field(default=None, ge=0)
    pattern_id: str | None = None
    tags: list[str] | None = Field(default=None, max_length=20)
    is_favorite: bool | None = None


class ExerciseOut(CamelModel):
    id: str
    name: str
    description: str
    difficulty: Difficulty
    estimated_duration_seconds: int
    target_count: int
    sets: int
    rounds: int
    rest_seconds: int
    pattern_id: str
    tags: list[str]
    is_favorite: bool


class DeviceSystemMetrics(CamelModel):
    cpu_usage_percent: float
    memory_usage_percent: float
    disk_usage_percent: float
    temperature_celsius: float
    uptime_seconds: float
    reported_at: datetime


class DeviceIn(CamelModel):
    name: str = Field(min_length=1, max_length=120)
    mac_address: str = Field(min_length=1, max_length=64)
    device_type: str = Field(default="", max_length=60)
    manufacturer: str = Field(default="", max_length=120)


class DeviceOut(CamelModel):
    id: str
    name: str
    mac_address: str
    device_type: str
    manufacturer: str
    last_seen_at: datetime | None
    metrics: DeviceSystemMetrics | None


class SessionIn(CamelModel):
    name: str = Field(default="", max_length=120)
    exercise_id: str | None = None
    device_id: str | None = None
    started_at: datetime | None = None


class SessionOut(CamelModel):
    id: str
    name: str
    exercise_id: str | None
    device_id: str | None
    state: SessionStatus
    started_at: datetime
    completed_at: datetime | None


class TelemetryEventIn(CamelModel):
    schema_version: Literal[1]
    event_id: str = Field(min_length=1, max_length=200)
    session_id: str
    event_type: TelemetryEventType
    timestamp: datetime
    device_timestamp: datetime | None = None
    target_id: str | None = Field(default=None, max_length=120)
    target_index: int | None = None
    coordinates: TargetPoint | None = None
    state: str | None = Field(default=None, max_length=40)
    metrics: dict[str, float] | None = None

    @field_validator("timestamp", "device_timestamp")
    @classmethod
    def assume_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class TelemetryEventOut(TelemetryEventIn):
    pass


class IngestResult(CamelModel):
    accepted: int
    duplicates: int
    state: SessionStatus


class SessionMetrics(CamelModel):
    session_id: str
    exercise_id: str | None
    started_at: datetime
    completed_at: datetime | None
    targets_attempted: int
    targets_completed: int
    targets_missed: int
    average_target_time_ms: float | None
    fastest_target_time_ms: float | None
    slowest_target_time_ms: float | None
    estimated_calories_burned: float | None = None


class AnalyticsSummary(CamelModel):
    total_sessions: int
    completed_sessions: int
    total_active_seconds: float
    targets_attempted: int
    targets_completed: int
    targets_missed: int
    accuracy_percent: float | None
    average_target_time_ms: float | None
    fastest_target_time_ms: float | None
    slowest_target_time_ms: float | None
