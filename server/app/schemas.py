from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from .models import AudioReplaceMode, EventType, HotSwapMode, JobStatus, LicenseTier, PresetType, ScheduleMode


class AssetCreate(BaseModel):
    name: str
    source_url: Optional[str] = None
    size_bytes: Optional[int] = None
    duration_seconds: Optional[int] = None
    thumbnail_path: Optional[str] = None
    audio_only: bool = False


class AssetRead(AssetCreate):
    id: int
    created_at: datetime


class DestinationCreate(BaseModel):
    name: str
    endpoint: str
    stream_key: Optional[str] = None
    enabled: bool = True


class DestinationRead(DestinationCreate):
    id: int
    created_at: datetime


class PresetCreate(BaseModel):
    name: str
    preset_type: PresetType = PresetType.copy
    video_bitrate: Optional[int] = None
    audio_bitrate: Optional[int] = None
    force_encode: bool = False
    audio_replace: AudioReplaceMode = AudioReplaceMode.none
    hot_swap: HotSwapMode = HotSwapMode.none


class PresetRead(PresetCreate):
    id: int
    created_at: datetime


class JobCreate(BaseModel):
    asset_id: int
    destination_id: int
    preset_id: int
    requested_at: Optional[datetime] = None


class JobRead(JobCreate):
    id: int
    status: JobStatus
    invalid_reason: Optional[str]
    created_at: datetime
    updated_at: datetime


class ScheduleCreate(BaseModel):
    job_id: int
    starts_at: datetime
    ends_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    mode: ScheduleMode = ScheduleMode.one_time
    loop: bool = False
    run_now: bool = False


class ScheduleRead(ScheduleCreate):
    id: int
    created_at: datetime
    last_run_at: Optional[datetime]


class SessionRead(BaseModel):
    id: int
    schedule_id: int
    job_id: int
    started_at: datetime
    ended_at: Optional[datetime]
    status: JobStatus
    ffmpeg_log_path: Optional[str]
    created_log_at: Optional[datetime]
    reason: Optional[str]


class EventLogRead(BaseModel):
    id: int
    session_id: Optional[int]
    job_id: Optional[int]
    schedule_id: Optional[int]
    event_type: EventType
    message: str
    created_at: datetime


class LicenseRead(BaseModel):
    tier: LicenseTier
    lease_expires_at: datetime
    grace_expires_at: Optional[datetime]
    install_id: str
    install_secret: str


class RunNowRequest(BaseModel):
    job_id: int
    schedule_id: Optional[int] = None


class DashboardSummary(BaseModel):
    streams: int
    assets: int
    destinations: int
    presets: int
    active_sessions: int
    invalid_jobs: int


class UploadResponse(BaseModel):
    asset_id: int
    thumbnail_path: Optional[str]
    analyzed_duration: Optional[int]
