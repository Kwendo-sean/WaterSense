# WaterSense AI

**Intelligence for every drop.**

WaterSense AI is a complete hackathon-grade water intelligence prototype. It ingests normalized readings from simulated or physical devices, persists telemetry, applies explainable domain rules plus an actual Isolation Forest anomaly model, forecasts water depletion, creates alerts, and streams updates over WebSocket to a cinematic public site and live operations dashboard.

> Prototype outputs are decision-support signals based on available telemetry. They do not replace certified laboratory testing or regulatory water-quality assessment. Seeded stations and telemetry are clearly identified as demonstrations, not active deployments.

## What is included

- Editorial, motion-led public landing page
- Dark real-time operations dashboard with Nairobi-area OpenStreetMap demo map
- 12 seeded demo stations and approximately 48 hours of history per station
- Station detail telemetry, risk history, deterministic AI explanation, and depletion forecast
- Alert center with acknowledge and resolve actions
- Network analytics and database-derived AI insights
- Mobile-first `/demo-control` presentation surface
- Continuous multi-station simulator with seven scenario presets
- FastAPI, SQLAlchemy, SQLite/PostgreSQL, Pydantic, WebSocket
- Hybrid configurable threshold, rate-change, baseline, and Isolation Forest risk engine
- Arduino serial bridge contract
- Backend test suite and Docker Compose stack

## Architecture

```text
Simulator / Arduino / ESP32 / field input
                 │ normalized JSON
                 ▼
        POST /api/v1/telemetry
                 │ validate + persist
                 ▼
   Rules + rates + baseline + Isolation Forest
                 │
        ┌────────┼─────────┐
        ▼        ▼         ▼
      Alerts  Forecasts  Explanations
        └────────┼─────────┘
                 ▼
          WebSocket /ws/live
                 ▼
       React operations dashboard
```

The simulator does not bypass the backend. Every synthetic reading is validated by the same Pydantic schema, stored in the database, assessed by the real risk pipeline, and broadcast through the same WebSocket intended for hardware.

## Stack

Frontend: React 19, TypeScript, Vite, Framer Motion, TanStack Query, Recharts, React Leaflet/OpenStreetMap, Lucide.

Backend: Python 3.12+, FastAPI, SQLAlchemy 2, Pydantic, SQLite by default, PostgreSQL-ready with psycopg, NumPy, scikit-learn Isolation Forest, native WebSocket.

## Run locally (non-Docker)

Requirements: Python 3.12+, Node 20+.

### 1. Backend

```bash
cd backend
python -m venv .venv
# Git Bash / macOS / Linux
source .venv/Scripts/activate  # Windows Git Bash
# source .venv/bin/activate    # macOS/Linux
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

On first start, `watersense.db` is created and seeded. API docs are at http://localhost:8000/docs and health is at http://localhost:8000/api/v1/health.

### 2. Frontend

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open:

- Landing page: http://localhost:5173/
- Live dashboard: http://localhost:5173/dashboard
- Presenter controls: http://localhost:5173/demo-control

## Run with Docker

```bash
docker compose up --build
```

This starts PostgreSQL, the backend on port 8000, and nginx-served frontend on port 5173. Data persists in the `watersense_db` volume.

## Environment

Copy `.env.example` if you need overrides. Important values:

- `DATABASE_URL`: defaults to `sqlite:///./watersense.db`
- `CORS_ORIGINS`: comma-separated frontend origins
- `SIMULATOR_ENABLED`: start continuous simulation with the API
- `SIMULATOR_INTERVAL_SECONDS`: emission interval, default 3
- `VITE_API_URL`: browser-visible backend origin
- `VITE_WS_URL`: browser-visible WebSocket endpoint

## API contract

A device sends:

```json
{
  "station_code": "WS-NBI-001",
  "timestamp": "2026-08-15T12:30:00Z",
  "metrics": {
    "ph": 7.12,
    "turbidity_ntu": 2.9,
    "temperature_c": 23.8,
    "conductivity_us_cm": 421,
    "tds_ppm": 211,
    "water_level_percent": 72,
    "flow_rate_l_min": 4.8
  },
  "device": {"source": "simulator", "battery_percent": 91}
}
```

Core endpoints include station CRUD, telemetry history/latest, risk history, forecasts, alert actions, dashboard summary/activity, and simulator lifecycle/scenario actions under `/api/v1`. Live events are sent from `/ws/live` as `telemetry:new`, `risk:new`, `station:status_changed`, `alert:new`, `alert:resolved`, and forecast updates.

## Simulator and incident triggers

The simulator starts automatically unless disabled. It emits every three seconds. From `/demo-control`, select a station and trigger:

- `NORMAL`
- `CONTAMINATION_EVENT`
- `TANK_DEPLETION`
- `LEAK_EVENT`
- `SENSOR_FAILURE`
- `HEAVY_RAIN`
- `RECOVERY`

You can also set manual pH, turbidity, conductivity, and water-level overrides. API example:

```bash
curl -X POST http://localhost:8000/api/v1/simulator/scenario \
  -H 'Content-Type: application/json' \
  -d '{"station_id":4,"scenario":"CONTAMINATION_EVENT","intensity":1}'
```

## Reliable hackathon demo flow

1. Open `/dashboard` on the projector. Confirm the `LIVE LINK` indicator.
2. Open `/demo-control` on a phone.
3. Select **WS-NBI-004 / Kibera Demo Node 04**.
4. Tap **CONTAMINATION**. Over roughly 15 seconds, turbidity and conductivity climb while pH drifts. Risk progresses through safe/watch/warning/critical as readings pass through the real API pipeline.
5. On the dashboard, show the changing map pin, event stream, alert count, and station status.
6. Open Node 04 to show the chart, detected factors, anomaly score, confidence, and recommended action.
7. Open a tank station to show its depletion forecast.
8. Tap **RECOVER** and show telemetry normalize.

For a perfectly clean first scene, tap **NORMAL** on Node 04 before beginning and allow several readings to settle.

## Risk and forecast behavior

The hybrid risk score combines configurable prototype thresholds, rate of change, recent history, Isolation Forest anomaly output, and water-level context. Risk bands are: safe 0–24, watch 25–49, warning 50–74, critical 75–100. Initial values are configurable prototype thresholds; a deployment must use the appropriate regulator and water-source context.

Forecasting smooths recent level history through linear regression, requires at least five meaningful declining readings, estimates time to a 15% reserve, and reports confidence from fit quality. Flat, rising, or insufficient data returns an explicit unavailable state.

## Tests and production build

```bash
cd backend
SIMULATOR_ENABLED=false python -m pytest -q

cd ../frontend
npm run build
```

## Arduino integration

`scripts/arduino_serial_bridge.py` reads one JSON object per serial line, normalizes metric fields, and forwards them to the standard endpoint.

Arduino line:

```json
{"station_code":"WS-PROTOTYPE-01","ph":7.08,"turbidity_ntu":3.1,"water_level_percent":64}
```

Install `pyserial`, create the station through `POST /api/v1/stations`, then run:

```bash
python -m pip install pyserial
python scripts/arduino_serial_bridge.py --port COM4 --baud 9600
```

An ESP32 can post the normalized API payload directly and does not require the serial bridge.

## Limitations

This is a decision-support prototype. Authentication/RBAC, regulator-specific profiles, production migrations, durable background queues, calibrated hardware, certified sensor QA, laboratory integrations, and production observability are intentionally outside hackathon scope. The OpenStreetMap view requires internet access; the rest of the dashboard degrades gracefully if map tiles are unavailable.

## Roadmap

- Signed device credentials and telemetry rate limiting
- Regulator/source-specific threshold profiles
- Alembic migration lifecycle and production observability
- Calibrated ESP32/LoRaWAN reference node
- Notification channels and escalation policies
- Authentication, organizations, roles, and audit trails
- More robust seasonal and weather-aware forecasting
