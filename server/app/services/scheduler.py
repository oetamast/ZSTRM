from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Optional
from sqlmodel import select
from ..config import settings
from ..database import get_session
from ..models import (
    EventLog,
    EventType,
    Job,
    JobStatus,
    LicenseTier,
    RunnerLock,
    Schedule,
    ScheduleMode,
    Session,
)
from .licensing import licensing_client
from .pipeline import build_pipeline_summary


class Scheduler:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None

    def _acquire_lock(self) -> bool:
        with get_session() as session:
            lock = session.exec(select(RunnerLock).where(RunnerLock.lock_name == "scheduler")).first()
            now = datetime.utcnow()
            if lock and lock.expires_at > now and lock.locked_by != settings.runner_id:
                return False
            expiration = now + timedelta(seconds=settings.scheduler_tick_seconds * 3)
            if lock is None:
                lock = RunnerLock(lock_name="scheduler", locked_by=settings.runner_id, expires_at=expiration)
            else:
                lock.locked_by = settings.runner_id
                lock.expires_at = expiration
                lock.locked_at = now
            session.add(lock)
            session.commit()
            return True

    def _record_event(self, schedule_id: int, job_id: int, event_type: EventType, message: str) -> None:
        with get_session() as session:
            session.add(
                EventLog(
                    schedule_id=schedule_id,
                    job_id=job_id,
                    event_type=event_type,
                    message=message,
                )
            )
            session.commit()

    def _should_run(self, schedule: Schedule) -> bool:
        now = datetime.utcnow()
        if schedule.mode == ScheduleMode.one_time:
            return schedule.starts_at <= now and (schedule.ends_at is None or now <= schedule.ends_at)
        planned_end = schedule.starts_at + timedelta(minutes=schedule.duration_minutes or 0)
        if schedule.ends_at and now > schedule.ends_at:
            return False
        if planned_end and now > planned_end and not schedule.loop:
            return False
        if schedule.mode == ScheduleMode.windowed and not schedule.loop and schedule.ends_at and schedule.ends_at > planned_end:
            return False
        return schedule.starts_at <= now

    def _validate_schedule(self, schedule: Schedule) -> Optional[str]:
        if schedule.mode == ScheduleMode.windowed and schedule.ends_at and schedule.duration_minutes:
            window_minutes = (schedule.ends_at - schedule.starts_at).total_seconds() / 60
            if window_minutes > schedule.duration_minutes and not schedule.loop:
                return "Loop required when window exceeds duration"
        return None

    def _start_session(self, schedule: Schedule, job: Job) -> Session:
        with get_session() as session:
            pipeline_summary = build_pipeline_summary(job)
            sess = Session(schedule_id=schedule.id, job_id=job.id, ffmpeg_log_path=pipeline_summary)
            job.status = JobStatus.running
            job.updated_at = datetime.utcnow()
            schedule.last_run_at = datetime.utcnow()
            session.add(sess)
            session.add(job)
            session.add(schedule)
            self._record_event(schedule.id, job.id, EventType.started, f"Session started with pipeline {pipeline_summary}")
            session.commit()
            session.refresh(sess)
            return sess

    def _complete_session(self, sess: Session, success: bool, reason: Optional[str] = None) -> None:
        with get_session() as session:
            db_sess = session.get(Session, sess.id)
            if db_sess:
                db_sess.status = JobStatus.completed if success else JobStatus.failed
                db_sess.ended_at = datetime.utcnow()
                db_sess.reason = reason
                session.add(db_sess)
                session.commit()

    def _retry_within_window(self, schedule: Schedule) -> bool:
        now = datetime.utcnow()
        if schedule.ends_at and now > schedule.ends_at:
            return False
        planned_end = schedule.starts_at + timedelta(minutes=schedule.duration_minutes or 0)
        if planned_end and now > planned_end and not schedule.loop:
            return False
        return True

    def _handle_invalid(self, job: Job, reason: str) -> None:
        job.status = JobStatus.invalid
        job.invalid_reason = reason
        job.updated_at = datetime.utcnow()
        with get_session() as session:
            session.add(job)
            session.add(
                EventLog(
                    job_id=job.id,
                    event_type=EventType.invalidated,
                    message=reason,
                )
            )
            session.commit()

    def _process_schedule(self, schedule: Schedule) -> None:
        with get_session() as session:
            job = session.get(Job, schedule.job_id)
        if job is None:
            return
        tier = licensing_client.get_tier()
        if tier == LicenseTier.basic and schedule.loop and schedule.mode == ScheduleMode.windowed:
            self._handle_invalid(job, "Looped windows require Premium or above")
            return
        invalid_reason = self._validate_schedule(schedule)
        if invalid_reason:
            self._handle_invalid(job, invalid_reason)
            return
        if not self._should_run(schedule):
            return
        session_obj = self._start_session(schedule, job)
        simulated_success = True
        self._complete_session(session_obj, simulated_success)

    async def _tick(self) -> None:
        while True:
            if not self._acquire_lock():
                await asyncio.sleep(settings.scheduler_tick_seconds)
                continue
            with get_session() as session:
                schedules = session.exec(select(Schedule)).all()
            for schedule in schedules:
                try:
                    self._process_schedule(schedule)
                except Exception as exc:  # pragma: no cover
                    self._record_event(schedule.id, schedule.job_id, EventType.retry, str(exc))
                    if self._retry_within_window(schedule):
                        await asyncio.sleep(settings.scheduler_tick_seconds)
                        self._process_schedule(schedule)
            await asyncio.sleep(settings.scheduler_tick_seconds)

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._tick())


scheduler = Scheduler()
