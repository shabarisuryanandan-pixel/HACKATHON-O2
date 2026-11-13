import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from supabase import Client, create_client

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
SQLITE_PATH = BASE_DIR / "app.db"

app = FastAPI(title="Hackathon Finale Base", version="0.1.0")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class NoteCreate(BaseModel):
    """Payload for saving a quick connectivity test record."""

    note: str = Field(..., min_length=1, max_length=200)


def get_sqlite_connection() -> sqlite3.Connection:
    """Open a SQLite connection with row dictionary access."""
    conn = sqlite3.connect(str(SQLITE_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_sqlite_db() -> None:
    """Ensure the local SQLite diagnostics table exists."""
    with get_sqlite_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS connectivity_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


init_sqlite_db()


def is_supabase_configured() -> bool:
    """Return True when both Supabase URL and API key are set."""
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()
    return bool(url and key)


def get_supabase_client() -> Optional[Client]:
    """Create and return a Supabase client if credentials are configured."""
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()
    if not url or not key:
        return None
    return create_client(url, key)


def check_supabase_live() -> dict[str, object]:
    """Verify Supabase client setup and live HTTP reachability."""
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = os.getenv("SUPABASE_KEY", "").strip()
    if not url or not key:
        return {"configured": False, "reachable": False, "detail": "Missing credentials"}

    client = get_supabase_client()
    if client is None:
        return {"configured": False, "reachable": False, "detail": "Client init failed"}

    try:
        response = httpx.get(
            f"{url}/auth/v1/health",
            headers={"apikey": key},
            timeout=5.0,
        )
        reachable = response.status_code == 200
        return {
            "configured": True,
            "reachable": reachable,
            "status_code": response.status_code,
        }
    except httpx.HTTPError as exc:
        return {
            "configured": True,
            "reachable": False,
            "detail": str(exc),
        }


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


@app.get("/health/db")
def database_health_check() -> dict[str, object]:
    """Verify Supabase client initialization and configuration status."""
    client = get_supabase_client()
    if client is None:
        return {"status": "unconfigured", "supabase_connected": False}
    return {"status": "ok", "supabase_connected": True}


@app.get("/api/diagnostics")
def run_diagnostics() -> dict[str, object]:
    """Check FastAPI backend, SQLite persistence, and live Supabase connectivity."""
    sqlite_ok = False
    sqlite_count = 0
    try:
        init_sqlite_db()
        with get_sqlite_connection() as conn:
            row = conn.execute("SELECT COUNT(*) AS total FROM connectivity_checks").fetchone()
            sqlite_count = int(row["total"]) if row else 0
            sqlite_ok = True
    except sqlite3.Error:
        sqlite_ok = False

    supabase_status = check_supabase_live()

    return {
        "backend": {
            "status": "ok",
            "environment": os.getenv("APP_ENV", "development"),
        },
        "sqlite": {
            "connected": sqlite_ok,
            "record_count": sqlite_count,
        },
        "supabase": supabase_status,
    }


@app.get("/api/notes")
def list_notes() -> dict[str, object]:
    """Return the latest 5 connectivity test records from SQLite."""
    init_sqlite_db()
    with get_sqlite_connection() as conn:
        rows = conn.execute(
            "SELECT id, note, created_at FROM connectivity_checks ORDER BY id DESC LIMIT ?",
            (5,),
        ).fetchall()
    return {
        "notes": [dict(row) for row in rows],
    }


@app.post("/api/notes")
def create_note(payload: NoteCreate) -> dict[str, object]:
    """Save a connectivity test record to SQLite using a parameterized query."""
    init_sqlite_db()
    clean_note = payload.note.strip()
    created_at = datetime.now(timezone.utc).isoformat()
    with get_sqlite_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO connectivity_checks (note, created_at) VALUES (?, ?)",
            (clean_note, created_at),
        )
        conn.commit()
        note_id = cursor.lastrowid
    return {
        "status": "saved",
        "id": note_id,
        "note": clean_note,
        "created_at": created_at,
    }
