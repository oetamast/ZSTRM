from __future__ import annotations

from datetime import datetime
from sqlmodel import select
from ..database import get_session
from ..models import EventLog, EventType, Job, JobStatus, LicenseTier, Preset
from .licensing import licensing_client


INVALID_PREMIUM_FEATURES = {
    "audio_replace": ["premium", "ultimate"],
    "hot_swap": ["premium", "ultimate"],
}


def invalidate_job(job: Job, reason: str) -> Job:
    job.status = JobStatus.invalid
    job.invalid_reason = reason
    job.updated_at = datetime.utcnow()
    with get_session() as session:
        session.add(job)
        session.add(EventLog(job_id=job.id, event_type=EventType.invalidated, message=reason))
        session.commit()
    return job


def evaluate_license(job: Job) -> Job:
    tier = licensing_client.get_tier()
    with get_session() as session:
        preset = session.get(Preset, job.preset_id)
    if preset is None:
        return invalidate_job(job, "Missing preset")
    if tier == LicenseTier.basic:
        if preset.audio_replace.value != "none":
            return invalidate_job(job, "Audio replace requires Premium")
        if preset.hot_swap.value != "none":
            return invalidate_job(job, "Hot swap requires Premium")
    if tier != LicenseTier.ultimate and preset.hot_swap.value == "immediate":
        return invalidate_job(job, "Immediate swaps require Ultimate")
    job.invalid_reason = None
    job.status = JobStatus.pending
    job.updated_at = datetime.utcnow()
    with get_session() as session:
        session.add(job)
        session.commit()
    return job


def downgrade_jobs() -> None:
    with get_session() as session:
        jobs = session.exec(select(Job)).all()
        for job in jobs:
            evaluate_license(job)
