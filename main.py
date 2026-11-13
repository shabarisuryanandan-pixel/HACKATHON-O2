import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Hackathon Finale Base", version="0.1.0")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def is_supabase_configured() -> bool:
    """Return True when both Supabase URL and API key are set."""
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()
    return bool(url and key)


@app.get("/")
def read_root() -> FileResponse:
    """Serve the frontend entry page."""
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/health")
def health_check() -> dict[str, object]:
    """Return basic service health and configuration status."""
    return {
        "status": "ok",
        "environment": os.getenv("APP_ENV", "development"),
        "supabase_configured": is_supabase_configured(),
    }
