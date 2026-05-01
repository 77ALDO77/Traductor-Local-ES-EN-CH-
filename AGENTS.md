# AGENTS.md — BoC Translator

## Commands

```bash
# Dev server (backend directly, no frontend build needed)
uv run main.py          # → http://localhost:8000

# Docker stack (full: backend + ollama + nginx serving React SPA)
./init-models.sh        # first-time: build, start, pull qwen2.5:3b
docker compose up -d    # subsequent starts
docker compose logs -f  # tail all services
docker compose restart  # restart services
docker compose down     # stop everything

# Frontend (React SPA)
cd frontend && npm run dev     # Vite dev server
cd frontend && npm run build   # output to dist/ (served by nginx in Docker)
cd frontend && npm run lint    # ESLint

# Dependencies
uv sync                   # sync venv with lockfile
uv run pytest             # run tests (none exist yet)
```

## Architecture

### Two frontend regimes (important!)
- **Docker/production**: nginx serves the React SPA (`frontend/dist/`) on `/`, proxying `/api/*` and `/static/*` to the FastAPI backend. The Jinja2 template routes in `main.py` are bypassed.
- **Local dev** (`uv run main.py`): FastAPI directly serves Jinja2 templates from `templates/`. The React SPA must be built and served separately via nginx or `npm run dev`.
- Both regimes call the same backend API at `/api/*`.

### Backend structure
- `main.py` — FastAPI app, lifespan, static mounts, HTTP routes
- `backend/routers/` — API endpoints (translation, documents, voice, admin)
- `backend/services/` — business logic, each exposes a module-level singleton:
  - `translation_service` (`ollama_service.py`) — Ollama Qwen integration
  - `document_service` (`document_service.py`) — DOCX/XLSX/PDF translation
  - `voice_service` (`voice_service.py`) — **disabled/dummy** (raises on all calls)
  - `audit_service` (`audit_service.py`) — CSV audit log, thread-safe
  - `pdf_translation_service.py` — PDF-specific translation (used by document_service)
- `backend/schemas/` — Pydantic models (translation, documents, voice)
- `backend/auth.py` — HTTP Basic Auth for admin routes
- `backend/utils.py` — `secure_wipe_and_delete()` (overwrites with random bytes)

### translator_engine/ (disabled)
A separate FastAPI microservice with CTranslate2 NMT and Faster-Whisper — commented out in `docker-compose.yml`. The voice service and `FastTranslationService` in `ollama_service.py` reference it but it's not running.

### Global singletons (no DI)
`translation_service`, `document_service`, `voice_service`, `audit_service` are all instantiated as module-level globals. Import them directly; there is no dependency injection framework.

## Key constraints

- **Python 3.11** (`.python-version`, `pyproject.toml`, Dockerfile). Ignore the README mention of 3.10.
- **`numpy<2.0`** pinned in `pyproject.toml` — do not upgrade numpy past 1.x.
- **Ollama must be running** and the model must be pulled before translation works. Run `ollama pull qwen2.5:3b` (or the MODEL_NAME in env).
- **FFmpeg must be installed** system-wide (used for audio conversion even though voice is disabled).
- **Voice features are entirely disabled** — both the backend voice router and websocket immediately return 503/error. Do not attempt to fix or enable them; this is intentional.
- **LibreOffice required in Docker** for DOCX→PDF conversion (installed in Dockerfile).
- **Admin auth** is HTTP Basic with env vars `ADMIN_USERNAME`/`ADMIN_PASSWORD`. Defaults in docker-compose are `admin_boc` / `seguridad_boc_2026`.
- **Audit logs** are CSV files in `uploads/audit/audit_log.csv`. Times are in `America/Lima` timezone.

## Package manager

**uv** with `uv.lock`. Sync with `uv sync --frozen --no-dev` in Docker, or `uv sync` locally. Not pip, not poetry, not conda.

## Languages supported

English ↔ Spanish ↔ Chinese (Simplified). The Language enum and prompt logic treat any "chinese"/"chino"/"mandarin" input as Simplified Chinese.

## Environment variables (non-obvious defaults)

| Variable | Default |
|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` |
| `MODEL_NAME` | `qwen2.5:3b` |
| `CLEANUP_INTERVAL_MINUTES` | `10` |
| `FILE_RETENTION_MINUTES` | `30` |
| `ADMIN_USERNAME` | `admin` |
| `ADMIN_PASSWORD` | `admin` |
| `LOG_LEVEL` | `INFO` |
