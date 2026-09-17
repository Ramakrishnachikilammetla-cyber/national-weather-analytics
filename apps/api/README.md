# National Weather Analytics API

FastAPI backend for the National Weather Big Data Analytics Platform (India).

This directory currently contains the **foundation only**: process liveness under `/api/v1/health`. There is no database connection, authentication, ingest, Kafka, Spark, ML, or scraping.

Contracts: `docs/ARCHITECTURE.md`, `docs/API_DESIGN.md`, `docs/DATABASE_DESIGN.md`, `docs/DEVELOPMENT_PLAN.md`.

## Requirements

- Python 3.12+

## Run locally

From the repository root:

```bash
python -m venv .venv
```

Windows (PowerShell):

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r apps/api/requirements.txt
cd apps/api
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

macOS / Linux:

```bash
source .venv/bin/activate
pip install -r apps/api/requirements.txt
cd apps/api
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Optional: copy `apps/api/.env.example` to `apps/api/.env` and adjust `ENVIRONMENT` or `APP_NAME`.

## Check liveness

```bash
curl http://127.0.0.1:8000/api/v1/health
```

Expected JSON includes `"status": "ok"`. OpenAPI docs: http://127.0.0.1:8000/docs

## Tests

From the repository root (with the venv activated and dependencies installed):

```bash
pytest
```

## Not in this phase

- PostgreSQL / PostGIS
- JWT auth and RBAC
- Weather ingest or sample weather rows
- Kafka, Spark, ML
- React frontend
