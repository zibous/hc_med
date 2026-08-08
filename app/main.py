"""hc_med – Laborwerte Dashboard (FastAPI App)."""

import logging
import os
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path

import yaml
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.infrastructure.database import DATA_ROOT, set_current_user, get_current_user

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = PROJECT_ROOT / "frontend" / "templates"
STATIC_DIR = PROJECT_ROOT / "frontend" / "static"
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ─── Logging Setup ──────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s %(message)s"

logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger("hc_med")

# File Handler (Rotation: 1MB, 3 Backups)
file_handler = RotatingFileHandler(
    LOG_DIR / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
file_handler.setLevel(LOG_LEVEL)
logging.getLogger().addHandler(file_handler)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("hc_med Dashboard gestartet")
    yield
    logger.info("hc_med Dashboard beendet")


app = FastAPI(title="hc_med", lifespan=lifespan)


# ─── Middleware: User aus Cookie setzen ──────────────────────────────────────────
@app.middleware("http")
async def user_context_middleware(request: Request, call_next):
    """Setzt den aktiven User aus dem Cookie 'hc_user' für jeden Request."""
    user = request.cookies.get("hc_user", "peter")
    set_current_user(user)
    response = await call_next(request)
    return response

# Static files
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Templates
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


# API Routers
from app.api.overview import router as overview_router  # noqa: E402
from app.api.gruppe import router as gruppe_router  # noqa: E402
from app.api.trend import router as trend_router  # noqa: E402
from app.api.verknuepfung import router as verknuepfung_router  # noqa: E402
from app.api.tests_router import router as tests_router  # noqa: E402
from app.api.kpidata import router as kpidata_router  # noqa: E402
from app.api.bericht import router as bericht_router  # noqa: E402
from app.api.pathologisch import router as pathologisch_router  # noqa: E402
from app.api.favoriten import router as favoriten_router  # noqa: E402
from app.api.vergleich import router as vergleich_router  # noqa: E402
from app.api.gesamtbericht import router as gesamtbericht_router  # noqa: E402
from app.api.alle_tests import router as alle_tests_router  # noqa: E402

app.include_router(overview_router)
app.include_router(gruppe_router)
app.include_router(trend_router)
app.include_router(verknuepfung_router)
app.include_router(tests_router)
app.include_router(kpidata_router)
app.include_router(bericht_router)
app.include_router(pathologisch_router)
app.include_router(favoriten_router)
app.include_router(vergleich_router)
app.include_router(gesamtbericht_router)
app.include_router(alle_tests_router)


@app.get("/api/status")
async def status():
    return {"status": "ok", "app": "hc_med", "user": get_current_user()}


@app.get("/api/patient")
async def patient_info():
    """Gibt die Patientendaten des aktiven Users zurück."""
    userlist_path = DATA_ROOT / "userlist.yaml"
    if not userlist_path.exists():
        return {}
    data = yaml.safe_load(userlist_path.read_text(encoding="utf-8")) or {}
    patients = data.get("patient", {})
    return patients.get(get_current_user(), {})


@app.get("/api/users")
async def list_users():
    """Gibt alle verfügbaren User zurück (für User-Auswahl im Frontend)."""
    userlist_path = DATA_ROOT / "userlist.yaml"
    if not userlist_path.exists():
        return {"users": [], "active": get_current_user()}
    data = yaml.safe_load(userlist_path.read_text(encoding="utf-8")) or {}
    patients = data.get("patient", {})
    users = []
    for key, info in patients.items():
        user_dir = DATA_ROOT / "user" / key
        users.append({
            "id": key,
            "vorname": info.get("vorname", ""),
            "nachname": info.get("nachname", ""),
            "hat_daten": (user_dir / "labor.db").exists(),
        })
    return {"users": users, "active": get_current_user()}


@app.post("/api/user/{user_id}")
async def switch_user(user_id: str, response: Response):
    """Wechselt den aktiven User – setzt Cookie."""
    user_dir = DATA_ROOT / "user" / user_id
    if not user_dir.is_dir():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"User '{user_id}' nicht gefunden")
    response.set_cookie("hc_user", user_id, max_age=60 * 60 * 24 * 365, httponly=False, samesite="lax")
    return {"ok": True, "user": user_id}
