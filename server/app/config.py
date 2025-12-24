from __future__ import annotations

import os
import uuid
from datetime import timedelta
from pydantic import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./zstrm.db"
    api_key: str = "dev-key"
    runner_id: str = os.getenv("HOSTNAME", str(uuid.uuid4()))
    license_endpoint: str = "https://licenses.example.com/renew"
    install_id: str = str(uuid.uuid4())
    install_secret: str = str(uuid.uuid4())
    scheduler_tick_seconds: int = 60
    licensing_grace_hours: int = 6
    licensing_retry_backoff_minutes: int = 5
    licensing_retry_window_minutes: int = 30
    license_lease_hours: int = 1

    class Config:
        env_file = ".env"


settings = Settings()
