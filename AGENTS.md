# AGENTS.md — BoC Translator

## Commands

```bash
# Docker stack (primary workflow: backend + vLLM + nginx serving React SPA)
docker compose up -d              # start all services
docker compose logs -f            # tail all services
docker compose logs -f backend    # tail backend only
docker compose restart            # restart services
docker compose down               # stop everything

# Local dev (backend only — requires separate vLLM instance)
uv run main.py                    # → http://localhost:8000
uv sync                           # sync venv with lockfile

# Frontend (React + TypeScript + Vite)
cd frontend && npm run dev        # Vite dev server
cd frontend && npm run build      # output to dist/ (served by nginx in Docker)
cd frontend && npm run lint       # ESLint
```

## Architecture

### LLM backend is vLLM, NOT Ollama
- The code uses `AsyncOpenAI` against vLLM's OpenAI-compatible API (`/v1` endpoint).
- Docker runs a `vllm` service (`vllm/vllm-openai`) with `Qwen/Qwen2.5-1.5B-Instruct`.
- The README mentions Ollama — **that is stale**. Ignore it.

### Two frontend regimes
- **Docker/production**: nginx serves the React SPA (`frontend/dist/`) on `/` with HTTPS (HTTP→HTTPS redirect). Proxies `/api/*` and `/static/*` to the FastAPI backend on port 8000.
- **Local dev** (`uv run main.py`): FastAPI serves plain HTML files via `FileResponse` from `templates/`. No Jinja2 rendering. The React SPA must be built and served separately.
- Both regimes call the same backend API at `/api/*`.

### Backend structure
- `main.py` — FastAPI app, lifespan (vLLM health check + file cleanup task), `FileResponse` HTML routes, static mount
- `backend/routers/` — `translation.py`, `documents.py`, `voice.py`, `admin.py`
- `backend/services/` — module-level singletons:
  - `llm_service.py` → `translation_service` (vLLM via OpenAI-compatible API, with retry logic)
  - `document_service.py` → `document_service` (DOCX/XLSX in-place XML editing; PDF via PDF→Word→translate→PDF)
  - `pdf_translation_service.py` — PDF-specific logic (used by document_service)
  - `audit_service.py` → `audit_service` (CSV audit log, thread-safe)
  - `voice_service.py` → `voice_service` (**disabled/dummy** — raises on all audio calls)
- `backend/schemas/` — Pydantic models
- `backend/auth.py` — HTTP Basic Auth for admin routes
- `backend/utils.py` — `secure_wipe_and_delete()`

### Global singletons (no DI)
`translation_service`, `document_service`, `voice_service`, `audit_service` are module-level globals. Import them directly.

### translator_engine/ (disabled)
A separate FastAPI microservice with CTranslate2 NMT and Faster-Whisper — commented out in `docker-compose.yml`. `FastTranslationService` in `llm_service.py` still references it but will fail if called.

## Key constraints

- **Python 3.11** (`pyproject.toml` `requires-python`, Dockerfile). README says 3.10 — **stale**.
- **`numpy<2.0`** pinned in `pyproject.toml` — do not upgrade past 1.x.
- **vLLM must be running** with the correct model before translation works. Docker handles this; local dev requires manual vLLM setup.
- **Local dev `LLM_HOST` default is `http://localhost:8000`** — this conflicts with FastAPI running on the same port. For local dev, set `LLM_HOST` to wherever vLLM actually listens (e.g. `http://localhost:8001` or an Ollama instance).
- **Voice features are disabled** — `voice_service` is a dummy that raises on all calls. Do not attempt to fix; this is intentional ("mantenimiento de hardware").
- **LibreOffice required in Docker** for DOCX→PDF conversion (installed in Dockerfile along with CJK fonts).
- **Admin auth** is HTTP Basic with `ADMIN_USERNAME`/`ADMIN_PASSWORD`. Docker defaults: `admin_boc` / `seguridad_boc_2026`.
- **HTTPS enforced in production** — nginx redirects HTTP→HTTPS with self-signed certs in `nginx/certs/`.
- **No tests exist** — `tests/` directory does not exist. `uv run pytest` will find nothing.

## Languages supported

English ↔ Spanish ↔ Simplified Chinese. The translation prompt logic treats any "chinese"/"chino"/"mandarin"/"zh"/"cn"/"zh-cn" input as Simplified Chinese.

## Environment variables

| Variable | Local default | Docker default |
|---|---|---|
| `LLM_HOST` | `http://localhost:8000` | `http://vllm:8000` |
| `MODEL_NAME` | `Qwen/Qwen2.5-1.5B-Instruct` | `Qwen/Qwen2.5-1.5B-Instruct` |
| `CLEANUP_INTERVAL_MINUTES` | `10` | `60` |
| `FILE_RETENTION_MINUTES` | `30` | `1440` (24h) |
| `ADMIN_USERNAME` | `admin` | `admin_boc` |
| `ADMIN_PASSWORD` | `admin` | `seguridad_boc_2026` |
| `LOG_LEVEL` | `INFO` | `INFO` |

## Package manager

**uv** with `uv.lock`. Sync with `uv sync --frozen --no-dev` in Docker, or `uv sync` locally. Not pip, not poetry, not conda.

## Frontend notes

- React 18 + TypeScript + Vite + TailwindCSS
- Pages: Dashboard, Documents, Voice (disabled UI), Login, AdminAudit
- `frontend/bun.lock` exists but `package-lock.json` is the primary lockfile
- Built output goes to `frontend/dist/`, mounted read-only into nginx at `/usr/share/nginx/html`
