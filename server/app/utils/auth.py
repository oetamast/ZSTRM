from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from ..config import settings

api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_api_key(api_key: str = Depends(api_key_scheme)) -> str:
    if api_key != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return api_key
