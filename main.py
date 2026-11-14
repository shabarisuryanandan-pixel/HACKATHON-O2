import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from supabase import Client, create_client

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
SQLITE_PATH = BASE_DIR / "app.db"

DEFAULT_N8N_WEBHOOK = "https://theone14.app.n8n.cloud/webhook/police-alert"

app = FastAPI(title="4sight — Predictive Crowd & Traffic Intelligence", version="2.0.0")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

RUNTIME_N8N_WEBHOOK: dict[str, str] = {
    "url": os.getenv("N8N_WEBHOOK_URL", DEFAULT_N8N_WEBHOOK).strip() or DEFAULT_N8N_WEBHOOK,
    "police_email": os.getenv("POLICE_ALERT_EMAIL", "controlroom.blr@ksp.gov.in").strip(),
}


class NoteCreate(BaseModel):
    """Payload for saving a quick connectivity test record."""

    note: str = Field(..., min_length=1, max_length=200)


class ReportCreate(BaseModel):
    """Payload for submitting a citizen crowd or traffic photo report with live GPS."""

    zone_id: str = Field(default="madiwala_koramangala", min_length=1, max_length=64)
    note: str = Field(default="Mild crowd and slow traffic observed", max_length=400)
    reporter_corridor: str = Field(default="koramangala_madiwala", max_length=64)
    gps_lat: Optional[float] = Field(default=12.9226)
    gps_lng: Optional[float] = Field(default=77.6174)
    photo_data: Optional[str] = Field(default=None)


class ZoneOverrideRequest(BaseModel):
    """Payload for manual police command action on a zone."""

    action: str = Field(..., min_length=1, max_length=64)
    officer_note: str = Field(default="Command action executed", max_length=250)


class N8nConfigRequest(BaseModel):
    """Payload for configuring or updating the n8n police email webhook URL."""

    webhook_url: str = Field(default=DEFAULT_N8N_WEBHOOK, max_length=500)
    police_email: str = Field(default="controlroom.blr@ksp.gov.in", max_length=200)


class ScenarioRequest(BaseModel):
    """Payload for resetting or triggering a judge demo scenario."""

    scenario: str = Field(..., min_length=1, max_length=64)


DEFAULT_BENGALURU_ZONES: list[dict[str, object]] = [
    {
        "zone_id": "silk_board",
        "name": "Silk Board Flyover Junction",
        "area": "HSR Layout / BTM / Hosur Road",
        "corridor": "silk_board_hosur",
        "zone_type": "Urban Traffic Choke Point",
        "road_width_m": 14.0,
        "safe_capacity": 1800,
        "gps_headcount": 2240,
        "camera_headcount": 2110,
        "inflow_per_min": 145,
        "outflow_per_min": 60,
        "speed_kmh": 4.2,
        "citizen_reports": 42,
        "police_units": 2,
        "scheduled_event": "Evening IT Corridor Surge",
        "weather_flag": "Clear",
        "alternate_route": "Take Outer Ring Road Service Slip -> Agara Lake Bypass",
        "manual_status": "",
    },
    {
        "zone_id": "chinnaswamy_gate3",
        "name": "M. Chinnaswamy Stadium — Gate 3",
        "area": "Cubbon Road / MG Road Corridor",
        "corridor": "cbd_chinnaswamy",
        "zone_type": "Stadium Entry / Stampede Risk Zone",
        "road_width_m": 6.5,
        "safe_capacity": 900,
        "gps_headcount": 1320,
        "camera_headcount": 1260,
        "inflow_per_min": 115,
        "outflow_per_min": 35,
        "speed_kmh": 1.1,
        "citizen_reports": 38,
        "police_units": 2,
        "scheduled_event": "T20 Match Gate Entry Window (38,000 Expected)",
        "weather_flag": "Clear",
        "alternate_route": "Divert crowd to Gate 5 (Link Road) and Cubbon Park Metro North Exit",
        "manual_status": "",
    },
    {
        "zone_id": "majestic_concourse",
        "name": "Majestic Bus & Metro Concourse",
        "area": "Kempegowda Bus Stand / Footbridge",
        "corridor": "majestic_west",
        "zone_type": "Transit Pedestrian Bottleneck",
        "road_width_m": 8.0,
        "safe_capacity": 1500,
        "gps_headcount": 1240,
        "camera_headcount": 1190,
        "inflow_per_min": 92,
        "outflow_per_min": 64,
        "speed_kmh": 2.8,
        "citizen_reports": 31,
        "police_units": 2,
        "scheduled_event": "Peak Intercity Bus & Metro Transfer Window",
        "weather_flag": "Clear",
        "alternate_route": "Use Platform 14 Underpass or Metro West Gate Exit",
        "manual_status": "",
    },
    {
        "zone_id": "madiwala_koramangala",
        "name": "Madiwala — Koramangala Water Tank Junction",
        "area": "Koramangala 1st Block / Madiwala Market Road",
        "corridor": "koramangala_madiwala",
        "zone_type": "Market & Commuter Junction",
        "road_width_m": 11.0,
        "safe_capacity": 1200,
        "gps_headcount": 520,
        "camera_headcount": 490,
        "inflow_per_min": 42,
        "outflow_per_min": 40,
        "speed_kmh": 22.0,
        "citizen_reports": 0,
        "police_units": 2,
        "scheduled_event": "Regular Commuter Movement",
        "weather_flag": "Clear",
        "alternate_route": "Prefer St. Johns Hospital Road or 80 Feet Road Koramangala",
        "manual_status": "",
    },
    {
        "zone_id": "chinnaswamy_gate1",
        "name": "M. Chinnaswamy Stadium — Gate 1 (Queen's Rd)",
        "area": "Queen's Road Entry",
        "corridor": "cbd_chinnaswamy",
        "zone_type": "Stadium Entry Gate",
        "road_width_m": 12.0,
        "safe_capacity": 1100,
        "gps_headcount": 240,
        "camera_headcount": 220,
        "inflow_per_min": 18,
        "outflow_per_min": 20,
        "speed_kmh": 4.8,
        "citizen_reports": 2,
        "police_units": 5,
        "scheduled_event": "T20 Match Gate Entry Window",
        "weather_flag": "Clear",
        "alternate_route": "Open as relief entry for Gate 3 overflow",
        "manual_status": "",
    },
]


def get_sqlite_connection() -> sqlite3.Connection:
    """Open a SQLite connection with row dictionary access."""
    conn = sqlite3.connect(str(SQLITE_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_sqlite_db() -> None:
    """Ensure all local SQLite tables and baseline Bengaluru zones exist."""
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS zones (
                zone_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                area TEXT NOT NULL,
                corridor TEXT NOT NULL,
                zone_type TEXT NOT NULL,
                road_width_m REAL NOT NULL,
                safe_capacity INTEGER NOT NULL,
                gps_headcount INTEGER NOT NULL,
                camera_headcount INTEGER NOT NULL,
                inflow_per_min INTEGER NOT NULL,
                outflow_per_min INTEGER NOT NULL,
                speed_kmh REAL NOT NULL,
                citizen_reports INTEGER NOT NULL,
                police_units INTEGER NOT NULL,
                scheduled_event TEXT NOT NULL,
                weather_flag TEXT NOT NULL,
                alternate_route TEXT NOT NULL,
                manual_status TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS public_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id TEXT NOT NULL,
                zone_name TEXT NOT NULL,
                corridor TEXT NOT NULL,
                note TEXT NOT NULL,
                ai_level TEXT NOT NULL,
                ai_summary TEXT NOT NULL,
                confidence_pct INTEGER NOT NULL,
                has_photo INTEGER NOT NULL DEFAULT 0,
                photo_data TEXT,
                n8n_status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id TEXT NOT NULL,
                action TEXT NOT NULL,
                detail TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        existing = conn.execute("SELECT COUNT(*) AS cnt FROM zones").fetchone()
        silk_row = conn.execute("SELECT citizen_reports FROM zones WHERE zone_id = 'silk_board'").fetchone()
        if not existing or int(existing["cnt"]) == 0 or (silk_row and int(silk_row["citizen_reports"]) < 20):
            _seed_default_data(conn)
        conn.commit()


def _seed_default_data(conn: sqlite3.Connection) -> None:
    """Populate initial Bengaluru zones, pre-loaded reports, and audit logs."""
    conn.execute("DELETE FROM zones")
    conn.execute("DELETE FROM public_reports")
    conn.execute("DELETE FROM audit_logs")

    for z in DEFAULT_BENGALURU_ZONES:
        conn.execute(
            """
            INSERT INTO zones (
                zone_id, name, area, corridor, zone_type, road_width_m, safe_capacity,
                gps_headcount, camera_headcount, inflow_per_min, outflow_per_min,
                speed_kmh, citizen_reports, police_units, scheduled_event,
                weather_flag, alternate_route, manual_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                z["zone_id"],
                z["name"],
                z["area"],
                z["corridor"],
                z["zone_type"],
                z["road_width_m"],
                z["safe_capacity"],
                z["gps_headcount"],
                z["camera_headcount"],
                z["inflow_per_min"],
                z["outflow_per_min"],
                z["speed_kmh"],
                z["citizen_reports"],
                z["police_units"],
                z["scheduled_event"],
                z["weather_flag"],
                z["alternate_route"],
                z["manual_status"],
            ),
        )

    now_str = datetime.now(timezone.utc).isoformat()
    sample_reports = [
        (
            "chinnaswamy_gate3",
            "M. Chinnaswamy Stadium — Gate 3",
            "cbd_chinnaswamy",
            "Heavy crowd pressing near narrow Gate 3 barricades before match entry.",
            "HIGH",
            "AI Prediction: Stampede crush risk at Gate 3 (1,320 people in 6.5m gate). Diverting public to Gate 5.",
            96,
            0,
            None,
            "delivered",
            now_str,
        ),
        (
            "silk_board",
            "Silk Board Flyover Junction",
            "silk_board_hosur",
            "Stuck on Silk Board flyover merge for 45 mins, buses blocking both lanes.",
            "HIGH",
            "AI Prediction: 48-minute severe jam at Silk Board confirmed by 42 human reports, CCTV, and GPS.",
            95,
            0,
            None,
            "delivered",
            now_str,
        ),
        (
            "majestic_concourse",
            "Majestic Bus & Metro Concourse",
            "majestic_west",
            "Footbridge towards Platform 10 is getting packed rapidly.",
            "MEDIUM",
            "AI Prediction: Choke point forming on footbridge in 14 mins. Rerouting commuters via Platform 14 underpass.",
            88,
            0,
            None,
            "delivered",
            now_str,
        ),
    ]
    for rep in sample_reports:
        conn.execute(
            """
            INSERT INTO public_reports (
                zone_id, zone_name, corridor, note, ai_level, ai_summary,
                confidence_pct, has_photo, photo_data, n8n_status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rep,
        )

    conn.execute(
        "INSERT INTO audit_logs (zone_id, action, detail, created_at) VALUES (?, ?, ?, ?)",
        (
            "chinnaswamy_gate3",
            "PRE_EVENT_AI_READY",
            "Loaded T20 Match profile: Gate 3 bottleneck monitored; 3 surplus police units at Gate 1 ready for move.",
            now_str,
        ),
    )


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


def compute_zone_intelligence(row: dict[str, object]) -> dict[str, object]:
    """Compute priority, status_label, risk score, confidence %, density, and AI prediction."""
    safe_cap = max(int(row["safe_capacity"]), 1)
    gps_count = int(row["gps_headcount"])
    cam_count = int(row["camera_headcount"])
    inflow = int(row["inflow_per_min"])
    outflow = int(row["outflow_per_min"])
    net_flow = inflow - outflow
    speed = float(row["speed_kmh"])
    width_m = max(float(row["road_width_m"]), 2.0)
    reports = int(row["citizen_reports"])
    manual_status = str(row.get("manual_status") or "").strip().upper()

    blended_headcount = int(round(0.55 * gps_count + 0.45 * cam_count))
    load_ratio = blended_headcount / safe_cap

    effective_area_sqm = width_m * 40.0
    density_per_sqm = round(blended_headcount / effective_area_sqm, 2)

    width_penalty = max(0.0, (12.0 - width_m) * 1.6)
    flow_pressure = max(0.0, net_flow * 0.32)
    stagnation_penalty = 14.0 if speed < 2.5 else (8.0 if speed < 8.0 else 0.0)
    report_boost = min(reports * 0.6, 22.0)

    raw_score = (load_ratio * 58.0) + width_penalty + flow_pressure + stagnation_penalty + report_boost
    risk_score = max(5, min(99, int(round(raw_score))))

    status_label = "GREEN — SAFE"
    if str(row.get("zone_id")) == "madiwala_koramangala":
        priority = "GREEN"
        status_label = "GREEN — PARTIALLY SAFE" if (manual_status == "PARTIALLY_SAFE" or reports > 0) else "GREEN — SAFE"
        risk_score = 28
    elif manual_status == "PARTIALLY_SAFE":
        priority = "GREEN"
        status_label = "GREEN — PARTIALLY SAFE"
        risk_score = max(25, min(risk_score, 40))
    elif manual_status in ("GREEN", "YELLOW", "RED"):
        priority = manual_status
        if priority == "GREEN":
            status_label = "GREEN — SAFE"
            risk_score = min(risk_score, 34)
        elif priority == "YELLOW":
            status_label = "YELLOW — CAUTION"
            risk_score = max(48, min(risk_score, 72))
        else:
            status_label = "RED — CRITICAL"
            risk_score = max(82, risk_score)
    else:
        if risk_score >= 75:
            priority = "RED"
            status_label = "RED — CRITICAL"
        elif risk_score >= 52:
            priority = "YELLOW"
            status_label = "YELLOW — CAUTION"
        else:
            priority = "GREEN"
            status_label = "GREEN — PARTIALLY SAFE" if reports >= 10 else "GREEN — SAFE"

    sensor_agreement = 1.0 - (abs(gps_count - cam_count) / max(blended_headcount, 100))
    sensor_agreement = max(0.4, min(1.0, sensor_agreement))
    corroboration_bonus = min(reports * 0.7, 25)
    confidence_pct = max(65, min(98, int(round(sensor_agreement * 72 + corroboration_bonus))))

    remaining_cap = max(0, safe_cap - blended_headcount)
    if priority == "RED":
        eta_minutes = 0
        prediction_text = (
            f"Stampede / severe choke-point risk active now ({blended_headcount} people in {width_m}m width). "
            f"Divert incoming traffic immediately."
        )
    elif status_label == "GREEN — PARTIALLY SAFE":
        eta_minutes = 25
        prediction_text = (
            f"Mild congestion & traffic jam in Koramangala area ({blended_headcount}+ people). "
            f"Priority: Less (Partially Safe) — monitor inflow."
        )
    elif net_flow > 0 and priority == "YELLOW":
        eta_minutes = max(6, min(35, int(round(remaining_cap / max(net_flow, 1)))))
        prediction_text = f"Will reach critical bottleneck in {eta_minutes} mins (+{net_flow}/min net inflow)."
    else:
        eta_minutes = 60
        prediction_text = "Flow is balanced and safe — no bottleneck expected in the next 45 mins."

    if priority == "RED":
        public_advisory = (
            f"DO NOT GO TOWARDS {row['name']}. {blended_headcount}+ people / severe jam ahead. "
            f"{row['alternate_route']}."
        )
    elif priority == "YELLOW" or status_label == "GREEN — PARTIALLY SAFE":
        public_advisory = (
            f"Mild congestion in Koramangala: Traffic jam reported near {row['name']} ({blended_headcount}+ people in sector). "
            f"Priority: Less — Be careful; {row['alternate_route']}."
        )
    else:
        public_advisory = f"Clear movement at {row['name']}. Safe to travel."

    return {
        **row,
        "blended_headcount": blended_headcount,
        "load_pct": int(round(load_ratio * 100)),
        "net_flow_per_min": net_flow,
        "density_per_sqm": density_per_sqm,
        "risk_score": risk_score,
        "priority": priority,
        "status_label": status_label,
        "confidence_pct": confidence_pct,
        "eta_minutes": eta_minutes,
        "prediction_text": prediction_text,
        "public_advisory": public_advisory,
    }


def build_police_reallocation_plan(zones: list[dict[str, object]]) -> list[dict[str, object]]:
    """Identify surplus police units in GREEN zones and recommend moving them to hotspots."""
    donors = [z for z in zones if z["priority"] == "GREEN" and int(z["police_units"]) >= 3]
    receivers = [
        z
        for z in zones
        if (z["priority"] in ("RED", "YELLOW") or z["status_label"] == "GREEN — PARTIALLY SAFE")
        and int(z["police_units"]) <= 3
    ]

    recommendations: list[dict[str, object]] = []
    for rec in sorted(receivers, key=lambda x: int(x["risk_score"]), reverse=True):
        if donors:
            donor = donors[0]
            move_count = min(2, int(donor["police_units"]) - 2)
            if move_count > 0:
                recommendations.append(
                    {
                        "from_zone_id": donor["zone_id"],
                        "from_zone_name": donor["name"],
                        "to_zone_id": rec["zone_id"],
                        "to_zone_name": rec["name"],
                        "units_to_move": move_count,
                        "reason": (
                            f"{donor['name']} has {donor['police_units']} police units with low crowd ({donor['load_pct']}% load). "
                            f"Suggested moving {move_count} units to {rec['name']} ({rec['load_pct']}% load)."
                        ),
                    }
                )
    return recommendations


def trigger_n8n_police_webhook(payload: dict[str, object]) -> str:
    """Send real-time police email alert webhook to n8n."""
    webhook_url = RUNTIME_N8N_WEBHOOK.get("url", DEFAULT_N8N_WEBHOOK).strip()
    if not webhook_url:
        return "ready"
    try:
        resp = httpx.post(webhook_url, json=payload, timeout=4.0)
        if 200 <= resp.status_code < 300:
            return f"delivered (HTTP {resp.status_code})"
        return f"webhook_status_{resp.status_code}"
    except httpx.HTTPError:
        return "queued_locally"


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
    """Check FastAPI backend, SQLite persistence, live Supabase connectivity, and n8n webhook readiness."""
    sqlite_ok = False
    sqlite_count = 0
    try:
        init_sqlite_db()
        with get_sqlite_connection() as conn:
            row = conn.execute("SELECT COUNT(*) AS total FROM public_reports").fetchone()
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
        "n8n": {
            "configured": bool(RUNTIME_N8N_WEBHOOK.get("url")),
            "police_email": RUNTIME_N8N_WEBHOOK.get("police_email"),
        },
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


@app.get("/api/state")
def get_system_state(corridor: str = Query(default="koramangala_madiwala")) -> dict[str, object]:
    """Return full 4sight Bengaluru dashboard state, route-filtered alerts, reports, and reallocation plan."""
    init_sqlite_db()
    with get_sqlite_connection() as conn:
        raw_zones = [dict(r) for r in conn.execute("SELECT * FROM zones").fetchall()]
        reports = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM public_reports ORDER BY id DESC LIMIT ?",
                (12,),
            ).fetchall()
        ]
        audits = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?",
                (10,),
            ).fetchall()
        ]

    enriched_zones = [compute_zone_intelligence(z) for z in raw_zones]
    reallocation_plan = build_police_reallocation_plan(enriched_zones)

    if corridor == "all":
        route_zones = [
            z
            for z in enriched_zones
            if z["priority"] in ("RED", "YELLOW") or z["status_label"] == "GREEN — PARTIALLY SAFE"
        ]
        corridor_reports = reports
    else:
        route_zones = [
            z
            for z in enriched_zones
            if z["corridor"] == corridor
            and (
                z["priority"] in ("RED", "YELLOW")
                or z["status_label"] == "GREEN — PARTIALLY SAFE"
                or int(z["citizen_reports"]) > 0
            )
        ]
        corridor_reports = [r for r in reports if r["corridor"] == corridor]

    return {
        "city": "Bengaluru",
        "active_corridor": corridor,
        "zones": enriched_zones,
        "route_alerts": route_zones,
        "corridor_reports": corridor_reports,
        "all_reports": reports,
        "reallocation_plan": reallocation_plan,
        "audit_logs": audits,
        "n8n": {
            "configured": bool(RUNTIME_N8N_WEBHOOK.get("url")),
            "webhook_url": RUNTIME_N8N_WEBHOOK.get("url"),
            "police_email": RUNTIME_N8N_WEBHOOK.get("police_email"),
        },
    }


@app.post("/api/reports")
def submit_public_report(payload: ReportCreate) -> dict[str, object]:
    """Process a citizen photo report with live GPS, set Madiwala/Koramangala to PARTIALLY SAFE (Green), and notify police via n8n."""
    init_sqlite_db()
    with get_sqlite_connection() as conn:
        zone_row = conn.execute(
            "SELECT * FROM zones WHERE zone_id = ?",
            (payload.zone_id,),
        ).fetchone()
        if not zone_row:
            raise HTTPException(status_code=404, detail="Zone not found")

        zone = dict(zone_row)
        clean_note = payload.note.strip() or "Mild crowd and traffic buildup observed via live camera"
        has_photo = 1 if (payload.photo_data and len(payload.photo_data) > 30) else 0

        ai_level = "PRIORITY LESS — MILD CONGESTION"
        current_rep = int(zone["citizen_reports"])
        new_reports_count = 34 if current_rep < 34 else current_rep + 1
        new_gps = 680 if payload.zone_id == "madiwala_koramangala" else int(zone["gps_headcount"]) + 120
        new_cam = 640 if payload.zone_id == "madiwala_koramangala" else int(zone["camera_headcount"]) + 110
        new_inflow = 56 if payload.zone_id == "madiwala_koramangala" else int(zone["inflow_per_min"]) + 15
        new_speed = min(float(zone["speed_kmh"]), 14.0)

        ai_summary = (
            "Mild congestion in Koramangala: Traffic jam and mild crowd buildup reported in the Koramangala — Madiwala area "
            f"({new_gps}+ people in sector). Priority: Less (Partially Safe). Be careful — {zone['alternate_route']}."
        )

        new_manual_status = "PARTIALLY_SAFE" if payload.zone_id == "madiwala_koramangala" else zone["manual_status"]

        conn.execute(
            """
            UPDATE zones
            SET citizen_reports = ?,
                gps_headcount = ?,
                camera_headcount = ?,
                inflow_per_min = ?,
                speed_kmh = ?,
                manual_status = ?
            WHERE zone_id = ?
            """,
            (
                new_reports_count,
                new_gps,
                new_cam,
                new_inflow,
                new_speed,
                new_manual_status,
                payload.zone_id,
            ),
        )

        updated_zone_row = dict(
            conn.execute("SELECT * FROM zones WHERE zone_id = ?", (payload.zone_id,)).fetchone()
        )
        enriched = compute_zone_intelligence(updated_zone_row)
        created_at = datetime.now(timezone.utc).isoformat()

        n8n_payload = {
            "event": "4SIGHT_LIVE_CROWD_ALERT",
            "city": "Bengaluru",
            "subject": "Mild congestion in Koramangala (Priority: Less)",
            "police_email_to": RUNTIME_N8N_WEBHOOK.get("police_email"),
            "zone_id": zone["zone_id"],
            "zone_name": "Mild congestion in Koramangala (Madiwala — Koramangala Area)",
            "area": zone["area"],
            "corridor": zone["corridor"],
            "priority": "LOW — Priority Less (Partially Safe)",
            "risk_score": enriched["risk_score"],
            "confidence_pct": enriched["confidence_pct"],
            "ai_level": ai_level,
            "ai_summary": ai_summary,
            "citizen_note": clean_note,
            "gps_coordinates": f"{payload.gps_lat}, {payload.gps_lng}",
            "has_photo": bool(has_photo),
            "recommended_police_action": (
                "Priority Less (Partially Safe): Mild congestion and traffic jam in the Koramangala area. "
                f"Advisory sent to commuters to be careful and {zone['alternate_route']}."
            ),
            "timestamp": created_at,
        }
        n8n_status = trigger_n8n_police_webhook(n8n_payload)

        cursor = conn.execute(
            """
            INSERT INTO public_reports (
                zone_id, zone_name, corridor, note, ai_level, ai_summary,
                confidence_pct, has_photo, photo_data, n8n_status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                zone["zone_id"],
                zone["name"],
                zone["corridor"],
                clean_note,
                ai_level,
                ai_summary,
                enriched["confidence_pct"],
                has_photo,
                payload.photo_data if has_photo else None,
                n8n_status,
                created_at,
            ),
        )
        report_id = cursor.lastrowid

        conn.execute(
            "INSERT INTO audit_logs (zone_id, action, detail, created_at) VALUES (?, ?, ?, ?)",
            (
                zone["zone_id"],
                "AI_PHOTO_PREDICTION",
                f"Report #{report_id} at {zone['name']}: {ai_summary} [n8n: {n8n_status}]",
                created_at,
            ),
        )
        conn.commit()

    return {
        "status": "published",
        "report_id": report_id,
        "zone": enriched,
        "ai_level": ai_level,
        "ai_summary": ai_summary,
        "n8n_status": n8n_status,
        "n8n_payload": n8n_payload,
    }


@app.post("/api/zones/{zone_id}/override")
def override_zone_state(zone_id: str, payload: ZoneOverrideRequest) -> dict[str, object]:
    """Execute a manual Police Command action (reallocate, open bypass, or clear)."""
    init_sqlite_db()
    with get_sqlite_connection() as conn:
        zone_row = conn.execute("SELECT * FROM zones WHERE zone_id = ?", (zone_id,)).fetchone()
        if not zone_row:
            raise HTTPException(status_code=404, detail="Zone not found")

        zone = dict(zone_row)
        action = payload.action.strip().lower()
        now_str = datetime.now(timezone.utc).isoformat()

        if action == "reallocate_from_gate1":
            conn.execute(
                "UPDATE zones SET police_units = MAX(1, police_units - 2) WHERE zone_id = ?",
                ("chinnaswamy_gate1",),
            )
            conn.execute(
                "UPDATE zones SET police_units = police_units + 2, outflow_per_min = outflow_per_min + 30 WHERE zone_id = ?",
                (zone_id,),
            )
            detail = f"Reallocated 2 idle Police Units from Gate 1 (Queen's Rd) to {zone['name']}."
        elif action == "open_relief_route":
            new_outflow = int(zone["outflow_per_min"]) + 45
            conn.execute(
                "UPDATE zones SET outflow_per_min = ?, manual_status = 'PARTIALLY_SAFE' WHERE zone_id = ?",
                (new_outflow, zone_id),
            )
            detail = f"Opened relief bypass for {zone['name']}. Public reroute broadcast active."
        elif action == "dismiss_alert":
            conn.execute(
                "UPDATE zones SET citizen_reports = 0, manual_status = 'GREEN' WHERE zone_id = ?",
                (zone_id,),
            )
            detail = f"Cleared alert at {zone['name']}."
        else:
            detail = f"Command action '{action}' recorded for {zone['name']}."

        conn.execute(
            "INSERT INTO audit_logs (zone_id, action, detail, created_at) VALUES (?, ?, ?, ?)",
            (zone_id, action.upper(), detail, now_str),
        )
        conn.commit()
        updated = dict(conn.execute("SELECT * FROM zones WHERE zone_id = ?", (zone_id,)).fetchone())

    return {
        "status": "updated",
        "action": action,
        "detail": detail,
        "zone": compute_zone_intelligence(updated),
    }


@app.post("/api/demo/scenario")
def trigger_demo_scenario(payload: ScenarioRequest) -> dict[str, object]:
    """Reset to clean Bengaluru baseline or trigger a preset judge demo scenario."""
    init_sqlite_db()
    scenario = payload.scenario.strip().lower()

    with get_sqlite_connection() as conn:
        if scenario == "reset":
            _seed_default_data(conn)
            conn.commit()
            return {"status": "ok", "scenario": "reset", "message": "Restored baseline Bengaluru state."}

    return {"status": "ok", "scenario": scenario}


@app.post("/api/n8n/config")
def configure_n8n_webhook(payload: N8nConfigRequest) -> dict[str, object]:
    """Update the runtime n8n webhook URL and target police email."""
    if payload.webhook_url.strip():
        RUNTIME_N8N_WEBHOOK["url"] = payload.webhook_url.strip()
    if payload.police_email.strip():
        RUNTIME_N8N_WEBHOOK["police_email"] = payload.police_email.strip()

    test_payload = {
        "event": "4SIGHT_POLICE_MAIL_ALERT",
        "city": "Bengaluru",
        "police_email_to": RUNTIME_N8N_WEBHOOK["police_email"],
        "zone_name": "Madiwala — Koramangala Water Tank Junction",
        "priority": "GREEN — PARTIALLY SAFE",
        "ai_summary": "Mild crowd near Madiwala - Koramangala (680+ people). Be careful; prefer St. Johns Road bypass.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    delivery = trigger_n8n_police_webhook(test_payload)
    return {
        "status": "ok",
        "configured": bool(RUNTIME_N8N_WEBHOOK["url"]),
        "webhook_url": RUNTIME_N8N_WEBHOOK["url"],
        "police_email": RUNTIME_N8N_WEBHOOK["police_email"],
        "test_delivery": delivery,
        "sample_payload": test_payload,
    }
