from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator
from sqlmodel import SQLModel, Session, create_engine
from .config import settings

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
