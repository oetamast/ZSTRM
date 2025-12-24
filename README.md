# ZSTRM

Live Streaming tools (Youtube Only, for now)

## Getting started

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn server.app.main:app --reload
```

Use `X-API-Key: dev-key` for authenticated requests.

## Components
- **FastAPI backend** with SQLModel persistence and Alembic scaffolding
- **Scheduler runner** enforcing minute-precision scheduling, retries, and single-runner locking
- **Licensing client** with lease renewal, grace handling, and feature gating
- **Dashboard stub** available at `/static/index.html`
