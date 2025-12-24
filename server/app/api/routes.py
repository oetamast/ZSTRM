from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from ..database import get_session
from ..models import Asset, Destination, EventLog, Job, Preset, Schedule, ScheduleMode, Session
from ..schemas import (
    AssetCreate,
    AssetRead,
    DashboardSummary,
    DestinationCreate,
    DestinationRead,
    EventLogRead,
    JobCreate,
    JobRead,
    PresetCreate,
    PresetRead,
    RunNowRequest,
    ScheduleCreate,
    ScheduleRead,
    SessionRead,
    UploadResponse,
)
from ..services.jobs import evaluate_license
from ..services.scheduler import scheduler
from ..utils.auth import get_api_key

router = APIRouter(dependencies=[Depends(get_api_key)])


@router.post("/assets", response_model=AssetRead)
def create_asset(payload: AssetCreate):
    if payload.size_bytes and payload.size_bytes > 500 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Assets limited to 500MB uploads")
    asset = Asset(**payload.dict())
    with get_session() as session:
        session.add(asset)
        session.commit()
        session.refresh(asset)
    return asset


@router.get("/assets", response_model=list[AssetRead])
def list_assets(query: str | None = None):
    with get_session() as session:
        q = select(Asset)
        if query:
            q = q.where(Asset.name.contains(query))
        return session.exec(q).all()


@router.post("/assets/{asset_id}/upload", response_model=UploadResponse)
def finish_upload(asset_id: int, analyzed_duration: int | None = None):
    with get_session() as session:
        asset = session.get(Asset, asset_id)
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        asset.duration_seconds = analyzed_duration
        asset.thumbnail_path = asset.thumbnail_path or f"/thumbnails/{asset_id}.jpg"
        session.add(asset)
        session.commit()
        return UploadResponse(asset_id=asset.id, thumbnail_path=asset.thumbnail_path, analyzed_duration=analyzed_duration)


@router.post("/destinations", response_model=DestinationRead)
def create_destination(payload: DestinationCreate):
    dest = Destination(**payload.dict())
    with get_session() as session:
        session.add(dest)
        session.commit()
        session.refresh(dest)
    return dest


@router.get("/destinations", response_model=list[DestinationRead])
def list_destinations():
    with get_session() as session:
        return session.exec(select(Destination)).all()


@router.post("/presets", response_model=PresetRead)
def create_preset(payload: PresetCreate):
    preset = Preset(**payload.dict())
    with get_session() as session:
        session.add(preset)
        session.commit()
        session.refresh(preset)
    return preset


@router.get("/presets", response_model=list[PresetRead])
def list_presets():
    with get_session() as session:
        return session.exec(select(Preset)).all()


@router.post("/jobs", response_model=JobRead)
def create_job(payload: JobCreate):
    job = Job(**payload.dict())
    with get_session() as session:
        session.add(job)
        session.commit()
        session.refresh(job)
    return evaluate_license(job)


@router.get("/jobs", response_model=list[JobRead])
def list_jobs(status: str | None = None):
    with get_session() as session:
        q = select(Job)
        if status:
            q = q.where(Job.status == status)
        return session.exec(q).all()


@router.post("/schedules", response_model=ScheduleRead)
def create_schedule(payload: ScheduleCreate):
    schedule = Schedule(**payload.dict())
    with get_session() as session:
        session.add(schedule)
        session.commit()
        session.refresh(schedule)
    if schedule.run_now:
        scheduler._process_schedule(schedule)
    return schedule


@router.get("/schedules", response_model=list[ScheduleRead])
def list_schedules():
    with get_session() as session:
        return session.exec(select(Schedule)).all()


@router.post("/run-now", response_model=SessionRead)
def run_now(payload: RunNowRequest):
    with get_session() as session:
        schedule = session.get(Schedule, payload.schedule_id) if payload.schedule_id else None
        job = session.get(Job, payload.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if schedule is None:
        schedule = Schedule(job_id=job.id, starts_at=datetime.utcnow(), mode=ScheduleMode.one_time, run_now=True)
        with get_session() as session:
            session.add(schedule)
            session.commit()
            session.refresh(schedule)
    scheduler._process_schedule(schedule)
    with get_session() as session:
        session_obj = session.exec(select(Session).where(Session.job_id == job.id).order_by(Session.id.desc())).first()
        if not session_obj:
            raise HTTPException(status_code=500, detail="Failed to create session")
        return session_obj


@router.get("/sessions", response_model=list[SessionRead])
def list_sessions():
    with get_session() as session:
        return session.exec(select(Session)).all()


@router.get("/events", response_model=list[EventLogRead])
def list_events():
    with get_session() as session:
        return session.exec(select(EventLog)).all()


@router.get("/dashboard", response_model=DashboardSummary)
def dashboard_summary():
    with get_session() as session:
        streams = session.exec(select(Session)).all()
        assets = session.exec(select(Asset)).all()
        destinations = session.exec(select(Destination)).all()
        presets = session.exec(select(Preset)).all()
        jobs = session.exec(select(Job)).all()
        invalid_jobs = [j for j in jobs if j.invalid_reason]
        active_sessions = [s for s in streams if s.status == "running"]
    return DashboardSummary(
        streams=len(streams),
        assets=len(assets),
        destinations=len(destinations),
        presets=len(presets),
        active_sessions=len(active_sessions),
        invalid_jobs=len(invalid_jobs),
    )
