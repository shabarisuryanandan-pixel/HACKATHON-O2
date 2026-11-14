# Project Knowledge Base: 4sight — Predictive Stampede & Severe Jam Early-Warning System

> **Purpose**: This document is the single source of truth for the team so everyone can work in parallel across backend, frontend, demo scenarios, and the judge pitch.

---

## 1. Problem Statement
Large public gatherings (stadium matches, theatre releases, festivals) and major urban choke points (such as Silk Board-style junctions) frequently escalate into **fatal stampedes** or **40–60 minute gridlocks**.

Why current systems fail:
1. **Reactive, not predictive**: Authorities only see a crisis after a crush or total gridlock has already formed.
2. **Blind spots**: Official CCTV cameras do not cover every side street, gate, or approach road.
3. **Unwarned inflow**: Incoming crowds and commuters keep walking or driving into a bottleneck because they have no real-time warning or alternate route guidance.
4. **Unstructured citizen alerts**: People stuck in dangerous jams have no fast, trusted way to warn both nearby commuters and emergency responders simultaneously.

---

## 2. Solution Overview: Two-Sided Early-Warning Loop
The system connects **ground-level public awareness** with **authority emergency dispatch** through a predictive risk engine.

### Side A: Authority Command Dashboard (Police, Fire, Venue Control)
- Displays live **Red / Yellow / Green** priority status across all monitored zones, gates, and approach roads.
- **Pre-Event Readiness**: Loads scheduled match/event profiles in advance to pre-arm thresholds and position units before crowds arrive.
- **Dynamic Police & Unit Reallocation**: Detects when police/marshals are stationed at quiet, low-risk entries (`GREEN`) and recommends moving them to overcrowded gates, potential fight/break-in hotspots, or accident zones (`YELLOW`/`RED`).
- **Accident & Blockage Response**: Instantly flags major accidents, stalled vehicles, or public-reported road/construction blockages and dispatches emergency units + alternate routes.
- Shows **Predictive Warnings** ("Zone will reach Red in ~12 minutes at current inflow") and **Signal Confidence %** (how many independent sources agree).
- Provides **1-Click Manual Overrides**: Acknowledge, Dispatch/Reassign Unit, Open Relief Route, or Dismiss False Alarm, with a full audit log.

### Side B: Public Safety & Crowdsourced Portal (Citizens & Commuters)
- **Zero-install browser/QR access** (plus future mobile app) so anyone at a venue or road junction can check safety or report an issue in under 15 seconds.
- **Actionable Alerts**: Instead of vague warnings, users receive clear guidance:
  - *"Avoid Silk Board Junction — 45 min gridlock reported. Take Alternate Route B."*
  - *"Do NOT approach Gate 3 — High crowd crush risk. Use Gate 5 (Green)."*
- **Live Crowd-Sourced Reporting**: Users stuck in a jam or dense crowd can submit a quick zone report (severity + short note + optional photo).

---

## 3. Predictive Risk Engine & Input Variables

### A. Core Three Signals
1. **Aggregated GPS / Mobility Headcount**: Anonymous count of active devices in the zone and moving toward the zone (similar to live traffic density).
2. **CCTV / Security Camera Density**: Automated or simulated headcount/density estimate from venue or traffic cameras.
3. **Corroborated Public Reports**: Geo-zone reports submitted by citizens on the ground.

### B. Additional Predictive, Geospatial & Context Variables
4. **Inflow vs. Outflow Rate (Net Flow)**: People or vehicles entering per minute minus those exiting per minute. Sustained positive net flow predicts a crush or jam 10–20 minutes early.
5. **Movement Speed / Stagnation Index**: Average walking or traffic speed. High density with near-zero movement indicates an active crush, accident, or gridlock.
6. **Road Width, Gate Width & Choke-Point Geometry**: Uses geospatial/map width metadata (lanes, road width in meters, narrow flyovers, stadium gate width) and public-reported construction/building blockages to compute true safe capacity.
7. **Scheduled Event & Match Readiness**: Pre-loads match schedules, showtimes, and peak-hour windows so the system prepares capacity rules and unit placement before the event starts.
8. **Incident Type & Environmental Multipliers**: Flags accidents, fights/break-in risks, rain/low visibility, and downstream choke-point spillover.
9. **Active Police / Responder Deployment**: Tracks how many units are currently stationed in each zone to spot under-utilized units in `GREEN` zones that can be reallocated to `YELLOW`/`RED` zones.

### C. Engine Outputs per Zone
- **Priority Level**: `GREEN` (Normal), `YELLOW` (Building Pressure / Caution), `RED` (Critical Crush, Accident, or Severe Jam Risk)
- **Risk Score**: `0` to `100`
- **Confidence Score**: `0%` to `100%` based on multi-signal agreement (Camera + GPS + Citizen Reports)
- **Estimated Time to Critical**: Projected minutes until `RED` if current net inflow continues
- **Unit Reallocation Suggestion**: Plain-English recommendation (e.g., *"Move 2 units from Gate 1 (Green, 18% load) to Gate 3 (Red, 92% load)"*)
- **Recommended Action**: Clear plain-English instruction for both authorities and the public

---

## 4. Anti-Spam, Trust & Privacy-First Security

### Preventing Fake Alarms & Panic
- **Multi-Signal Corroboration**: A single citizen report never triggers a `RED` alert on its own; it opens a `Watch` state with low confidence until corroborated by 2–3+ independent reports, GPS density, or camera counts.
- **Rate Limiting & Deduplication**: Multiple submissions from the same session/device within a short window count as one report.
- **Human-in-the-Loop Override**: Police and fire operators can manually verify, escalate, or dismiss any alert at any time.

### Privacy & Security Guardrails
- **Zero Personal Tracking**: No individual GPS trails, phone numbers, or identities are stored. All mobility and camera counts are **aggregated at the zone level**.
- **No Facial Recognition**: Camera inputs are treated strictly as anonymous headcount/density numbers.
- **Authenticated Control Endpoints**: Authority overrides and sensor ingestion routes are separated from public reporting routes.

---

## 5. System Architecture & Tech Stack
- **Backend**: Python + FastAPI + Uvicorn (`main.py`)
- **Frontend**: HTML5 + Tailwind CSS + Vanilla JavaScript (`static/index.html`)
- **Visualizations**: Interactive SVG Zone/Route Schematic + Chart.js (inflow vs. outflow & density trends)
- **Persistence**: Supabase (persistent cloud database) + SQLite (fast local fallback/cache with parameterized queries)
- **Automation (Optional)**: n8n webhooks for emergency/alert notifications
- **Deployment**: GitHub (`main`) -> Render auto-deploy

---

## 6. Parallel Team Workstreams

### Track 1: Backend & Risk Engine
- Implement zone state store, predictive risk scoring function (`GREEN`/`YELLOW`/`RED` + `ETA to Red` + `Confidence %`), and anti-spam report deduplication.
- Build API endpoints (`GET /api/zones`, `POST /api/reports`, `POST /api/sensors/ingest`, `POST /api/incidents/{id}/override`, `GET /api/analytics`).
- Maintain `tests/test_app.py` with FastAPI `TestClient` checks ensuring all routes return HTTP 200.

### Track 2: Frontend Command & Public Views
- **Authority View**: Interactive SVG map of zones/gates/roads, Red/Yellow/Green live status cards, Chart.js trend graph, and manual dispatch/override controls.
- **Public View**: Mobile-friendly alert banner (showing active Red/Yellow zones + alternate routes) and a 15-second report submission form.
- Keep all tabs and views manual on click, typography clean and minimal, and zero emojis in UI or code.

### Track 3: Demo Scenarios & Data Simulation
- Prepare 3 realistic live demo presets (clickable from a Demo Control bar):
  1. **Normal Flow (All Green)**: Baseline stadium/junction state.
  2. **Early Warning (Gate 3 / Silk Board Surge)**: Rising GPS + inflow + 3 citizen reports -> turns Yellow/Red with 12-min warning and alternate route guidance.
  3. **False Alarm Test**: 1 isolated citizen report with low GPS/camera density -> stays low-confidence Watch and can be dismissed by Police override.

### Track 4: Pitch Deck & Judge Q&A
- Prepare a 3-minute story around real incidents (Chinnaswamy/theatre rushes and Silk Board jams).
- Highlight **early prevention via diversion**, **anti-spam multi-signal trust**, and **privacy-safe zone aggregation**.
- Clearly state that camera/GPS feeds use an open ingestion API powered by simulated venue data for the hackathon demo.

---

## 7. Planned API Contract (Draft)
- `GET /api/zones` — Current risk status, density, net inflow, confidence %, and alternate route for all zones.
- `POST /api/reports` — Submit a public crowd/jam report for a zone (rate-limited, triggers corroboration check).
- `POST /api/sensors/ingest` — Ingest updated camera count, GPS headcount, speed, and weather/event flags for a zone.
- `POST /api/zones/{zone_id}/override` — Authority manual action (`acknowledge`, `dispatch`, `reroute`, `dismiss`).
- `GET /api/analytics` — Time-series inflow/density data for Chart.js and recent audit log entries.


---

## 8. Judging Criteria Alignment Strategy (100 Marks)

| Criterion | Marks | How 4sight Wins Full Marks |
| :--- | :---: | :--- |
| **Problem Discovery and Research** | 15 | Ground the pitch in documented real-world failures: stadium/theatre stampedes (e.g., Chinnaswamy, Hyderabad Pushpa 2 crowd crush) and 40–60 minute urban choke points (e.g., Silk Board). Show the exact root causes: reactive CCTV monitoring, unwarned crowd inflow, and police units stuck in low-risk zones. |
| **Opportunity Identification** | 15 | Highlight the missing link between **top-down city/venue sensors** and **bottom-up citizen awareness**. Existing maps only show traffic after a jam forms and do not warn pedestrian crowds or reallocate police units dynamically. |
| **Innovation and Originality** | 20 | 1) **Pre-crisis predictive diversion** (predicts Red state 10–20 mins early via Net Inflow vs. Safe Capacity). 2) **Multi-signal corroboration** (GPS + Camera + 2–3 Citizen Reports) to eliminate false panic. 3) **Dynamic Police Reallocation** (moving idle units from Green entries to Red/Yellow hotspots). 4) **Road/Gate Width Geometry** + public construction/accident reporting. |
| **Technical Depth and Architecture** | 20 | Clean, modular **FastAPI** backend with deterministic predictive scoring, parameterized **SQLite** + **Supabase** cloud persistence, **interactive SVG** zone/choke-point schematic, **Chart.js** inflow/density analytics, anti-spam rate limiting, privacy-safe zone-level aggregation (no personal tracking/face recognition), and automated `TestClient` verification. |
| **Prototype Functionality** | 15 | Live, hosted web app on Render (`https://hackathon-o2.onrender.com`) where judges can test both the **Authority Command Dashboard** (Red/Yellow/Green triage, police unit reallocation, manual overrides) and the **Public Portal** (live reroute warnings + 15-second incident reporting + 1-click demo scenarios). |
| **Scalability and Real-World Impact** | 10 | Zero-install QR/browser access for the public, open sensor ingestion API compatible with any existing CCTV headcount or traffic feed, lightweight payloads for congested event networks, and clear rollout path from single stadiums/junctions to city-wide police/fire command centers. |
| **Presentation** | 5 | Crisp 3-minute narrative: Real Tragedy -> Root Cause -> Live Demo (Normal -> Surge Prediction -> Police Reallocation & Public Reroute -> False Alarm Dismissal) -> Privacy & Scalability takeaway. |
