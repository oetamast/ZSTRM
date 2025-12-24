from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
from sqlmodel import Field, SQLModel


class LicenseTier(str, Enum):
    basic = "basic"
    premium = "premium"
    ultimate = "ultimate"


class Asset(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    source_url: Optional[str] = None
    size_bytes: Optional[int] = None
    duration_seconds: Optional[int] = None
    thumbnail_path: Optional[str] = None
    audio_only: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Destination(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    endpoint: str
    stream_key: Optional[str] = None
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PresetType(str, Enum):
    copy = "copy"
    encode = "encode"


class AudioReplaceMode(str, Enum):
    none = "none"
    external_loop = "external_loop"
    video_only = "video_only"


class HotSwapMode(str, Enum):
    none = "none"
    immediate = "immediate"
    next_loop = "next_loop"


class Preset(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    preset_type: PresetType = Field(default=PresetType.copy)
    video_bitrate: Optional[int] = None
    audio_bitrate: Optional[int] = None
    force_encode: bool = False
    audio_replace: AudioReplaceMode = Field(default=AudioReplaceMode.none)
    hot_swap: HotSwapMode = Field(default=HotSwapMode.none)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    failed = "failed"
    completed = "completed"
    cancelled = "cancelled"
    invalid = "invalid"


class Job(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    asset_id: int = Field(foreign_key="asset.id")
    destination_id: int = Field(foreign_key="destination.id")
    preset_id: int = Field(foreign_key="preset.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    status: JobStatus = Field(default=JobStatus.pending)
    invalid_reason: Optional[str] = None
    requested_at: Optional[datetime] = None


class ScheduleMode(str, Enum):
    one_time = "one_time"
    windowed = "windowed"


class Schedule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="job.id")
    starts_at: datetime
    ends_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    mode: ScheduleMode = Field(default=ScheduleMode.one_time)
    loop: bool = False
    run_now: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_run_at: Optional[datetime] = None


class Session(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    schedule_id: int = Field(foreign_key="schedule.id")
    job_id: int = Field(foreign_key="job.id")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    status: JobStatus = Field(default=JobStatus.running)
    ffmpeg_log_path: Optional[str] = None
    created_log_at: Optional[datetime] = None
    reason: Optional[str] = None


class EventType(str, Enum):
    started = "started"
    stopped = "stopped"
    retry = "retry"
    invalidated = "invalidated"
    downgraded = "downgraded"
    upgraded = "upgraded"


class EventLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: Optional[int] = Field(default=None, foreign_key="session.id")
    job_id: Optional[int] = Field(default=None, foreign_key="job.id")
    schedule_id: Optional[int] = Field(default=None, foreign_key="schedule.id")
    event_type: EventType
    message: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LicenseState(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tier: LicenseTier = Field(default=LicenseTier.basic)
    install_id: str
    install_secret: str
    lease_expires_at: datetime
    grace_expires_at: Optional[datetime] = None
    last_checked_at: datetime = Field(default_factory=datetime.utcnow)


class RunnerLock(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    lock_name: str = Field(index=True)
    locked_by: str
    locked_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
