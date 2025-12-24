from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Optional
import httpx
from sqlmodel import select
from ..config import settings
from ..database import get_session
from ..models import EventLog, EventType, LicenseState, LicenseTier


def _load_license() -> LicenseState:
    with get_session() as session:
        state = session.exec(select(LicenseState)).first()
        if state is None:
            state = LicenseState(
                tier=LicenseTier.basic,
                install_id=settings.install_id,
                install_secret=settings.install_secret,
                lease_expires_at=datetime.utcnow(),
            )
            session.add(state)
            session.commit()
            session.refresh(state)
        return state


async def renew_license(state: LicenseState) -> LicenseState:
    payload = {"install_id": state.install_id, "secret": state.install_secret}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(settings.license_endpoint, json=payload, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            state.tier = LicenseTier(data.get("tier", state.tier.value))
            state.lease_expires_at = datetime.utcnow() + timedelta(hours=settings.license_lease_hours)
            state.grace_expires_at = None
            result_event = EventType.upgraded
        except Exception:
            state.grace_expires_at = datetime.utcnow() + timedelta(hours=settings.licensing_grace_hours)
            result_event = EventType.downgraded
    with get_session() as session:
        persisted = session.exec(select(LicenseState)).first()
        if persisted:
            for field in ["tier", "lease_expires_at", "grace_expires_at"]:
                setattr(persisted, field, getattr(state, field))
            persisted.last_checked_at = datetime.utcnow()
            session.add(persisted)
            session.add(
                EventLog(
                    event_type=result_event,
                    message=f"License {result_event.value} at {datetime.utcnow().isoformat()}",
                )
            )
            session.commit()
            session.refresh(persisted)
            state = persisted
    return state


class LicensingClient:
    def __init__(self) -> None:
        self.state: LicenseState = _load_license()
        self._task: Optional[asyncio.Task] = None

    def get_tier(self) -> LicenseTier:
        now = datetime.utcnow()
        if self.state.lease_expires_at < now:
            if self.state.grace_expires_at and self.state.grace_expires_at > now:
                return self.state.tier
            return LicenseTier.basic
        return self.state.tier

    def downgrade_if_needed(self) -> None:
        if self.get_tier() == LicenseTier.basic and self.state.tier != LicenseTier.basic:
            self.state.tier = LicenseTier.basic
            from .jobs import downgrade_jobs

            with get_session() as session:
                db_state = session.exec(select(LicenseState)).first()
                if db_state:
                    db_state.tier = LicenseTier.basic
                    db_state.grace_expires_at = datetime.utcnow() + timedelta(hours=settings.licensing_grace_hours)
                    session.add(db_state)
                    session.add(
                        EventLog(
                            event_type=EventType.downgraded,
                            message="Automatic downgrade after grace window",
                        )
                    )
                    session.commit()
            downgrade_jobs()

    async def _run(self) -> None:
        retry_deadline = datetime.utcnow() + timedelta(minutes=settings.licensing_retry_window_minutes)
        while True:
            now = datetime.utcnow()
            if now >= self.state.lease_expires_at:
                self.downgrade_if_needed()
            try:
                self.state = await renew_license(self.state)
                retry_deadline = datetime.utcnow() + timedelta(minutes=settings.licensing_retry_window_minutes)
            except Exception:
                if datetime.utcnow() > retry_deadline:
                    self.downgrade_if_needed()
                await asyncio.sleep(settings.licensing_retry_backoff_minutes * 60)
                continue
            await asyncio.sleep(settings.license_lease_hours * 3600)

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())


licensing_client = LicensingClient()
