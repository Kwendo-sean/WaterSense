# Pitch ↔ Reality Alignment

Reconciles the Strathmore household-pitch strategy (Raspberry Pi framing) with what we
actually have — the Arduino Uno kit in [HARDWARE.md](HARDWARE.md) — and with what's
already built and deployed in this repo. The pitch document's own standard is "don't
claim what isn't demonstrated" — this file applies that standard to its own hardware
and software claims.

## Corrected architecture (Arduino, not Raspberry Pi)

```
Physical water tank
        │  water level changes
        ▼
HC-SR04 ultrasonic sensor        ← on hand, zero additional cost
        │  distance reading
        ▼
Arduino Uno R3                   ← on hand
        │  Serial.println() one JSON line per reading
        ▼  USB cable, tethered to a laptop at the demo table
scripts/arduino_serial_bridge.py ← already in this repo
        │  HTTPS POST
        ▼
FastAPI backend                  ← already built & deployed
        │
        ▼
PostgreSQL (Docker, on the VPS)  ← already deployed
        │
        ▼
React dashboard                  ← already built & deployed, live now
  https://watersense.selenos.world
```

No WiFi on the Uno — the demo rig needs a laptop at the table, not a battery-only box
across the room. That's a real constraint, not a limitation of the pitch's ambition:
the KSh 75,000 "Hardware and prototype components" line in the funding ask is exactly
where an ESP32 or Pi Zero W (WiFi-capable, no tether) belongs as the next step —
frame it as *funded by the ask*, not as something already built.

## Corrected implementation stack table

Replaces Section 3's "Recommended implementation stack" table in the pitch doc:

| Layer | Pitch doc said | What we actually have / are using |
|---|---|---|
| Hardware | Raspberry Pi + sensor | Arduino Uno R3 + HC-SR04 ultrasonic level sensor, both on hand |
| Connectivity | WiFi, local buffering on outage | None on the Uno — USB-tethered to a laptop running the bridge script. WiFi (ESP32/Pi Zero W) is the proposed next-step, fundable from the ask |
| Device software | Python sensor-reading service | Arduino C++ sketch → one JSON line per reading over serial → `scripts/arduino_serial_bridge.py` (Python, already in repo) forwards to the API |
| Backend | Python + FastAPI | **Already built and running** — `backend/app/main.py` |
| Database | SQLite → Postgres | **Already deployed** — Postgres in Docker on the VPS |
| Dashboard | Responsive web app | **Already built and live** — `https://watersense.selenos.world/dashboard` |
| Analytics | pandas/scikit-learn | **Already implemented**: `calculate_forecast()` — linear regression depletion forecast, is literally Model A. `assess_risk()` — threshold + rate-of-change + Isolation Forest anomaly scoring, is Model B, already past the doc's proposed Stage 1 |

## What's already real vs. still proposed — use this to calibrate every slide

The pitch doc is careful to separate aspiration from evidence (good instinct — keep
doing that). Here's the actual state, so the separation is accurate:

**Already true, can be stated as fact and demoed live:**
- A working FastAPI backend with a real database, deployed and publicly reachable.
- A real depletion-forecast model (linear regression, requires 5+ declining readings,
  reports confidence from fit quality) — this is Model A, implemented, not aspirational.
- A real anomaly/risk model (deterministic thresholds + rate-of-change + Isolation
  Forest) — this is Model B, implemented, not aspirational.
- A live, responsive dashboard showing level, trend, and forecast.
- A real device-ingest pipeline: any source (simulator, Arduino, manual) goes through
  the identical validated API path — this directly supports the doc's own claim that
  "the system should not depend on uninterrupted internet merely to collect
  measurements" once buffering is added to the sketch.

**Still proposed / not yet true — keep saying so:**
- Sensor accuracy has not been validated against manual reference measurements
  (Section 6's "Level measurement" test — not yet run).
- Forecast error has not been measured against real observed depletion times
  (Section 6's "Depletion forecasting" test — not yet run; the model runs, but nobody
  has checked if its predictions were right).
- No household pilot, no customer interviews conducted yet.
- No unit-economics or supplier pricing confirmed.
- WiFi/production-grade connectivity does not exist yet (Arduino is tethered).

Saying "the forecasting and anomaly models are built and running against live
telemetry; we have not yet validated their accuracy against real household outcomes"
is both stronger and more honest than treating the whole analytics layer as
not-yet-built. Use that framing.

## Demo staging recommendation

The repo's existing dashboard seeds **12 simulated Nairobi stations** (a civic water-
quality network) — that's the right dataset for a different pitch (the hackathon spec
in `WATERSENSE_AI_MASTER_BUILD_SPEC.md`), but it's the *wrong* visual for this
household-single-tank pitch: showing a 12-node ops-center dashboard while describing
"a household tank" overstates scope and will draw questions you don't want.

For the Strathmore pitch specifically: seed or filter to **one tank-type station**,
feed it from the real HC-SR04 reading (or a short recorded session if live hardware
is risky on the day), and keep the live view narrow — level, trend, forecast,
one anomaly alert. That matches the "live tank-level reading + a forecast of when it
reaches a low threshold" demo the doc itself recommends in Section 12 as the strongest
possible demonstration.

If these two pitches (hackathon civic-network vs. Strathmore household) are being
presented to different audiences, that's fine — same backend, same models, two
different front-end narratives/datasets. Worth keeping explicit so nothing gets
conflated on the day.
