"""hc_med – Laborwerte Dashboard (FastAPI App)."""

import logging
import os
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

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

# Static files
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Templates
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


# API Router
from app.api.labor import router as labor_router  # noqa: E402

app.include_router(labor_router)


@app.get("/api/status")
async def status():
    return {"status": "ok", "app": "hc_med"}


@app.get("/api/patient")
async def patient_info():
    from app.api.labor import PATIENT_CONFIG
    return PATIENT_CONFIG
