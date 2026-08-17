# WaterSense AI — Master Build Specification

> **Purpose:** This file is the single source of truth for the coding agent. Build the complete WaterSense AI prototype from this specification. Do not stop at mockups. Implement the backend, database, simulation layer, AI/risk engine, real-time dashboard, and public landing page as a coherent working application.

---

## 1. Product Overview

**WaterSense AI** is an intelligent water-monitoring platform designed for communities, utilities, schools, boreholes, tanks, rivers, and other water sources.

The platform receives telemetry from physical monitoring nodes or simulated devices, analyzes the readings, detects anomalies, estimates contamination risk, forecasts water depletion, and presents everything in a polished real-time dashboard.

The initial hackathon prototype must work **without physical sensors**. It must include a realistic sensor simulator so the software is completely demonstrable now. Later, an Arduino or ESP32 should be able to replace the simulator without requiring architectural changes.

### Core idea

```text
Physical Sensor / Arduino / Simulator
                ↓
          Telemetry API
                ↓
        Validation + Storage
                ↓
      AI / Risk Analysis Engine
                ↓
      Alerts + Forecasting Layer
                ↓
        Real-Time WebSocket
                ↓
         React Dashboard
```

The system must be **sensor-source agnostic**.

Every data source should ultimately send the same normalized telemetry payload.

---

# 2. Hackathon Goal

The application should make a judge understand the problem and the solution in under 30 seconds.

The key demo story:

1. Dashboard initially shows several healthy water stations.
2. Live telemetry is visibly updating.
3. A selected station begins experiencing abnormal readings.
4. Its risk state changes from **SAFE → WARNING → CRITICAL**.
5. Charts animate to show the spike.
6. WaterSense AI generates an explanation of what changed.
7. An alert appears.
8. The system recommends an operational response.
9. A depletion forecast shows when the water source may reach a critical level.
10. The user can open a map and see which stations require intervention.

The product must feel like a **real civic infrastructure platform**, not a student admin dashboard.

---

# 3. Brand Direction

## Name

**WaterSense AI**

Possible supporting line:

**Intelligence for every drop.**

Alternative lines:

- Know your water before it becomes a crisis.
- Real-time intelligence for safer water systems.
- Detect. Predict. Protect.
- Water infrastructure that thinks ahead.

Use **“Intelligence for every drop.”** as the default.

---

# 4. Landing Page — Visual Direction

The public landing page should take inspiration from the **elegance, theatrical motion, editorial typography, bold composition, and experimental technical feel** of the Nous Research Hermes Agent site:

https://hermes-agent.nousresearch.com/

Do **not** clone the Hermes website.

Instead, translate its design philosophy into the WaterSense brand.

The resulting page should feel:

- experimental
- premium
- technical
- editorial
- cinematic
- intelligent
- slightly futuristic
- not corporate SaaS-template-like
- not generic Tailwind cards everywhere
- not filled with excessive gradients

## Desired design language

Use a strong combination of:

- oversized editorial serif headlines
- precise monospaced labels
- large whitespace
- asymmetric layouts
- diagrams and telemetry as art
- thin technical lines
- animated water/ripple/topographic motifs
- restrained UI chrome
- strong visual hierarchy
- elegant scroll-based reveals
- subtle grain/noise texture
- high-quality transitions

### Color system

Primary concept:

- Deep water / midnight: `#061A24`
- Electric cyan: `#23D5E7`
- Aqua: `#72F2E4`
- Soft off-white: `#F3F4EE`
- Signal green: `#55E68A`
- Warning amber: `#F7B955`
- Critical coral/red: `#FF5E5B`

The landing hero may use a bold saturated **electric blue/cyan field** similar in visual confidence to Hermes, but WaterSense should remain its own identity.

Avoid making the entire application blue.

The dashboard should use a darker, calmer operational palette.

---

# 5. Landing Page Structure

## 5.1 Navigation

Minimal top navigation.

Left:
- WaterSense AI logo/wordmark

Center or right:
- Platform
- Technology
- Impact
- Demo

Primary CTA:
- **Open Live Dashboard →**

Sticky navigation should become slightly translucent/blurred after scrolling.

---

## 5.2 Hero

The hero needs to feel memorable.

Small mono eyebrow:

`WATER INTELLIGENCE • REAL-TIME MONITORING`

Huge serif headline:

**KNOW YOUR WATER  
BEFORE IT BECOMES  
A CRISIS**

Supporting copy:

> WaterSense AI transforms live water telemetry into contamination warnings, infrastructure insights, and predictive alerts — before small changes become public-health emergencies.

CTAs:

- **Explore Live System**
- `See how it works ↓`

### Hero visual

Do not use a stock water photograph as the primary hero.

Create an abstract interactive visualization representing a water-monitoring network.

Ideas:

- animated contour lines
- radial sensor waves
- flowing particle field
- topographic river pattern
- nodes connected by fine animated lines
- a central water droplet represented as a scientific wireframe
- telemetry numbers appearing around the composition

Mouse movement can gently distort the water field.

The visual must remain performant.

---

## 5.3 Live intelligence strip

Below hero, create a horizontally moving data strip:

```text
PH 7.12    TURBIDITY 2.8 NTU    CONDUCTIVITY 412 µS/cm
NODE 07 SAFE    WATER LEVEL 74%    RISK 08%
```

Animate continuously but subtly.

---

## 5.4 Problem section

Headline:

**Water problems rarely begin as emergencies.  
They begin as signals nobody saw.**

Explain that water systems may experience contamination, abnormal turbidity, falling reservoir levels, pump failures, or unusual consumption before an obvious crisis occurs.

Visual: animated chart transitioning from normal telemetry into a spike.

---

## 5.5 How WaterSense works

Editorial numbered sequence similar to a premium feature-preview story.

### #01 Sense

**Every source becomes observable.**

Nodes collect data such as pH, turbidity, conductivity, temperature, flow, and water level.

### #02 Understand

**AI recognizes what humans may miss.**

The platform compares current measurements with historical behavior and expected ranges.

### #03 Predict

**Act before a threshold becomes a crisis.**

Forecast depletion, detect abnormal patterns, and estimate developing risk.

### #04 Respond

**Turn signals into decisions.**

Operators receive alerts, explanations, confidence scores, and recommended actions.

Each section should have its own animated technical visualization.

---

## 5.6 Product showcase

Create a dramatic browser/dashboard mock frame embedded into the page.

When the user scrolls into this section:

- dashboard scales gently from 0.92 → 1
- UI widgets enter sequentially
- a station on the map moves from green → amber → red
- an alert slides into view

Headline:

**FROM RAW SIGNALS  
TO CLEAR DECISIONS**

---

## 5.7 Hardware-agnostic section

Headline:

**Built for the sensors you have.  
Ready for the sensors you add.**

Explain:

- Prototype simulator
- Arduino Uno
- ESP32
- LoRaWAN nodes
- Existing utility telemetry
- Manual field testing

Use a diagram:

```text
Arduino ─┐
ESP32 ───┤
LoRa ────┤
Manual ──┼──→ WaterSense API → AI Engine → Dashboard
Simulator┘
```

---

## 5.8 Impact section

Emphasize potential use cases:

- community boreholes
- schools
- apartment tanks
- rural water points
- rivers
- utilities
- farms
- emergency-response teams

Do not invent real deployment statistics.

Use clearly marked **prototype/demo metrics** where necessary.

---

## 5.9 Final CTA

Large minimal section.

**EVERY DROP LEAVES A SIGNAL.  
WATERSENSE LISTENS.**

Button:

**Launch Dashboard →**

---

# 6. Motion and Interaction System

Motion is essential to the landing page.

Use **Framer Motion** and CSS transforms.

Potentially use lightweight Canvas/WebGL only where it genuinely improves the hero.

Required motion:

- smooth page transitions
- text reveal masks
- scroll-triggered section reveals
- animated line drawing
- floating telemetry
- hover microinteractions
- fluid button arrows
- animated chart stroke
- subtle parallax
- map-node pulse
- signal waves
- changing numerical counters

Respect:

```css
@media (prefers-reduced-motion: reduce)
```

Never allow animation to compromise readability.

Do not add random bouncing elements.

---

# 7. Application Architecture

Recommended monorepo:

```text
watersense/
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── features/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── lib/
│   │   ├── services/
│   │   ├── types/
│   │   └── assets/
│   └── ...
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── ml/
│   │   ├── websocket/
│   │   ├── simulator/
│   │   ├── core/
│   │   └── main.py
│   ├── tests/
│   └── ...
│
├── scripts/
├── docs/
├── docker-compose.yml
├── .env.example
└── README.md
```

---

# 8. Technology Stack

## Frontend

- React
- TypeScript
- Vite
- Tailwind CSS
- Framer Motion
- Recharts
- Leaflet + OpenStreetMap
- TanStack Query
- Zustand if lightweight global state is needed
- Lucide icons

Avoid excessive third-party dependencies.

## Backend

- Python
- FastAPI
- SQLAlchemy
- Pydantic
- Alembic
- SQLite in development
- PostgreSQL-ready architecture
- WebSockets

## AI / Data

- pandas
- numpy
- scikit-learn
- Isolation Forest for anomaly detection
- lightweight forecasting algorithm for water-level depletion

Do not add an LLM dependency just to call the platform “AI”.

The ML layer should actually compute something.

---

# 9. Core Data Models

## Station

```text
id
station_code
name
description
station_type
latitude
longitude
location_text
status
installed_at
last_seen_at
source_type
created_at
updated_at
```

`source_type`:

```text
simulator
arduino
esp32
manual
external
```

`station_type`:

```text
borehole
tank
river
reservoir
tap
school
community_point
other
```

---

## TelemetryReading

```text
id
station_id
timestamp

ph
turbidity_ntu
temperature_c
conductivity_us_cm
tds_ppm
water_level_percent
flow_rate_l_min

battery_percent
signal_strength

source
raw_payload
```

Not every field must be populated.

---

## RiskAssessment

```text
id
station_id
reading_id
timestamp

overall_risk_score
risk_level

ph_score
turbidity_score
conductivity_score
water_level_score
anomaly_score

detected_factors
explanation
recommended_action
confidence
model_version
```

Risk level:

```text
safe
watch
warning
critical
```

---

## Alert

```text
id
station_id
created_at
updated_at
resolved_at

severity
type
title
message
recommended_action

acknowledged
resolved
```

---

## Forecast

```text
id
station_id
created_at
forecast_type
forecast_for
predicted_value
confidence
metadata
```

---

# 10. Telemetry API

Primary endpoint:

```http
POST /api/v1/telemetry
```

Example:

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
  "device": {
    "source": "simulator",
    "battery_percent": 91
  }
}
```

Response:

```json
{
  "accepted": true,
  "reading_id": "...",
  "station_status": "safe",
  "risk_score": 8,
  "assessment_id": "..."
}
```

---

# 11. Required API Endpoints

```text
GET    /api/v1/health

GET    /api/v1/stations
POST   /api/v1/stations
GET    /api/v1/stations/{id}
PATCH  /api/v1/stations/{id}

POST   /api/v1/telemetry
GET    /api/v1/stations/{id}/telemetry
GET    /api/v1/stations/{id}/latest

GET    /api/v1/alerts
PATCH  /api/v1/alerts/{id}/acknowledge
PATCH  /api/v1/alerts/{id}/resolve

GET    /api/v1/stations/{id}/risk
GET    /api/v1/stations/{id}/forecast

GET    /api/v1/dashboard/summary
GET    /api/v1/dashboard/activity

POST   /api/v1/simulator/start
POST   /api/v1/simulator/stop
POST   /api/v1/simulator/scenario
GET    /api/v1/simulator/status
```

---

# 12. WebSocket

Provide:

```text
/ws/live
```

Events:

```text
telemetry:new
station:status_changed
risk:new
alert:new
alert:resolved
forecast:updated
```

Example event:

```json
{
  "event": "station:status_changed",
  "data": {
    "station_id": "...",
    "station_code": "WS-NBI-004",
    "previous": "safe",
    "current": "critical",
    "risk_score": 89,
    "timestamp": "..."
  }
}
```

The frontend should update without reloading.

---

# 13. Risk Engine

Build an explainable hybrid risk engine.

Do not rely exclusively on one ML model.

Use:

1. domain threshold rules
2. rate-of-change analysis
3. historical baseline comparison
4. Isolation Forest anomaly detection
5. combined risk scoring

The prototype is **decision-support**, not a certified drinking-water test.

The UI should make this clear.

## Example scoring logic

Normalize each risk component to `0–100`.

Weighted combined score:

```text
turbidity       25%
pH              20%
conductivity    15%
anomaly model   20%
rate of change  10%
context         10%
```

Make weights configurable.

Suggested risk mapping:

```text
0–24   SAFE
25–49  WATCH
50–74  WARNING
75–100 CRITICAL
```

---

# 14. Threshold Configuration

Do not hardcode all health standards into UI components.

Keep threshold profiles in backend configuration.

Example:

```python
{
    "ph": {
        "ideal_min": 6.5,
        "ideal_max": 8.5
    },
    "turbidity_ntu": {
        "warning": 5,
        "critical": 10
    }
}
```

These initial values should be treated as configurable prototype thresholds.

Add a note that deployed systems should use thresholds appropriate to the relevant regulator and water-source context.

---

# 15. AI Explanations

Generate deterministic explanations from detected factors.

Example:

**High contamination risk**

> Turbidity increased from 2.4 NTU to 14.8 NTU within 18 minutes while conductivity moved 31% above this station's recent baseline. The combined change is unusual for Node 04 and has triggered a critical anomaly score.

Recommended action:

> Temporarily flag the source for verification and conduct appropriate water-quality testing before normal consumption continues.

Do not claim that the software has definitively detected bacteria or pathogens unless actual appropriate sensors/testing exist.

---

# 16. Anomaly Detection

Implement Isolation Forest.

Features may include:

```text
ph
turbidity
temperature
conductivity
tds
water_level
flow_rate
ph_rate_change
turbidity_rate_change
conductivity_rate_change
```

For new stations with insufficient history:

- use threshold rules
- label ML confidence lower
- gradually enable baseline anomaly scoring once enough readings exist

Store model version.

---

# 17. Water Depletion Forecast

This is important for the demo.

Use recent water-level history to estimate depletion.

Prototype approach:

- rolling smoothing
- calculate recent slope
- simple linear regression
- estimate time to configurable critical level

Output:

```text
Current level: 43%
Critical threshold: 15%
Estimated critical level: 19h 24m
Confidence: 78%
```

Avoid generating a forecast when data is insufficient or trend is not meaningful.

---

# 18. Sensor Simulator

The simulator is a first-class feature, not an afterthought.

It should be capable of creating realistic telemetry for multiple stations.

Default frequency:

```text
every 3 seconds
```

Configurable.

## Scenario presets

### NORMAL

Stable safe readings.

### CONTAMINATION_EVENT

Over several steps:

- turbidity climbs sharply
- pH drifts
- conductivity increases
- risk progressively changes

Do not immediately jump from safe to critical.

### TANK_DEPLETION

Water level gradually decreases.

### LEAK_EVENT

- water level falls faster than expected
- flow behavior becomes abnormal

### SENSOR_FAILURE

- frozen values
- missing fields
- impossible spikes

### RECOVERY

Readings gradually return toward baseline.

### HEAVY_RAIN

Simulate post-rainfall turbidity and conductivity changes.

---

# 19. Hidden Demo Control Panel

Create:

```text
/demo-control
```

This is extremely important for hackathon presentation.

It should be visually simple and usable from a phone.

Allow the presenter to:

- select station
- start/stop simulator
- trigger scenario
- control scenario intensity
- manually set pH
- manually set turbidity
- manually set conductivity
- manually set water level
- return station to normal
- trigger fake hardware connection state

Large touch-friendly buttons:

```text
NORMAL
CONTAMINATION
LOW WATER
LEAK
SENSOR FAILURE
RECOVER
```

When triggered, the public dashboard changes in real time.

---

# 20. Dashboard Design Philosophy

The dashboard is an **operations center**, not a generic admin template.

It should feel like:

- infrastructure intelligence
- control room
- scientific monitoring
- premium modern software

Avoid:

- giant rounded cards everywhere
- random gradients
- excessive glassmorphism
- generic sidebar template
- emoji-heavy design

Use:

- thin borders
- dense but readable telemetry
- monospaced numerical values
- subtle grids
- status indicators
- restrained shadows
- excellent spacing
- purposeful motion

---

# 21. Dashboard Navigation

Desktop:

```text
Overview
Network
Stations
Alerts
Analytics
AI Insights
Simulator
System
```

Bottom:

```text
Demo Mode
Settings
```

Mobile navigation can collapse.

---

# 22. Dashboard — Overview

Top header:

```text
WATER NETWORK / LIVE
Last sync: 2 seconds ago
```

Primary status:

```text
NETWORK HEALTH
87 / 100
```

Summary:

```text
12 Stations
9 Safe
1 Watch
1 Warning
1 Critical
```

Secondary metrics:

```text
Avg pH
Avg Turbidity
Water Availability
Active Alerts
```

---

# 23. Network Map

Use Leaflet + OpenStreetMap.

Default prototype region can contain Nairobi-area demo stations.

Create seeded demo stations with plausible locations but clearly treat them as **demo stations**, not claimed active deployments.

Pin states:

- green = safe
- cyan = watch
- amber = warning
- red = critical
- grey = offline

Critical stations should have a subtle pulsing ring.

Clicking a station opens a compact preview:

```text
Kibera Demo Node 04
CRITICAL · Risk 87%

pH          6.1
Turbidity   14.8 NTU
Level       38%

View station →
```

---

# 24. Live Incident Panel

Display latest incidents.

Example:

```text
14:31:22
NODE 04
Turbidity anomaly
2.7 → 14.8 NTU

14:30:54
NODE 04
Risk level elevated
WARNING → CRITICAL
```

Animate new items in smoothly.

---

# 25. Station Details Screen

Header:

```text
WS-NBI-004
Kibera Demo Node 04

● CRITICAL
Risk 87%
Updated 2s ago
```

Main telemetry blocks:

- pH
- Turbidity
- Conductivity
- Temperature
- TDS
- Water Level
- Flow

Each metric:

- current value
- unit
- trend
- sparkline
- state

---

# 26. Historical Charts

Interactive timeframe:

```text
1H
6H
24H
7D
30D
```

Charts:

- pH
- turbidity
- conductivity
- water level
- overall risk

Show threshold bands where useful.

Allow synchronized crosshair.

---

# 27. AI Insight Panel

Example:

```text
WATERSENSE AI

CRITICAL RISK
87%

What changed
Turbidity rose 448% in 18 minutes.
Conductivity is 31% above recent baseline.
pH moved outside this node's configured normal band.

Pattern
The combined change is statistically unusual compared
with this station's recent telemetry.

Recommended action
Flag the source for verification and conduct appropriate
water-quality testing before normal use continues.

Confidence
91%
```

This panel should feel important and premium.

---

# 28. Alert Center

Filters:

```text
All
Critical
Warning
Watch
Resolved
```

Each alert contains:

- station
- time
- severity
- type
- concise explanation
- recommended action
- acknowledge
- resolve

---

# 29. Analytics

Include:

- network risk trend
- alerts by category
- stations ranked by risk
- water-level depletion
- anomaly frequency
- sensor uptime
- readings processed

Use believable demo data.

Never claim actual public impact from simulated telemetry.

---

# 30. AI Insights Page

Network-wide insights.

Example cards:

```text
3 stations show rising turbidity
2 tanks may fall below 20% within 24 hours
Node 08 telemetry appears unreliable
North cluster risk increased 18% over 6 hours
```

Each insight should be derived from database data.

---

# 31. Station Connection States

Support:

```text
LIVE
DEGRADED
OFFLINE
SIMULATED
MANUAL
```

Show source type transparently.

For the hackathon prototype, simulated nodes should be marked subtly:

`SIM`

Do not misrepresent simulated telemetry as live deployed hardware.

---

# 32. Future Arduino Integration Contract

The hardware bridge should eventually send the same API schema.

Possible architecture:

```text
Arduino Uno
    ↓ USB serial
Python serial bridge
    ↓ HTTP
POST /api/v1/telemetry
```

Example Arduino serial output:

```json
{
  "station_code": "WS-PROTOTYPE-01",
  "ph": 7.08,
  "turbidity_ntu": 3.1,
  "water_level_percent": 64
}
```

A Python bridge normalizes and forwards it.

Create a placeholder:

```text
scripts/arduino_serial_bridge.py
```

Document expected serial format.

Do not require Arduino to run the application.

---

# 33. Database Seed Data

Seed approximately:

```text
12 stations
48 hours of historical readings
3 resolved alerts
2 active alerts
multiple risk assessments
forecast data
```

Include station states:

```text
8–9 safe
1 watch
1 warning
1 critical
```

At least one water-level forecast.

---

# 34. Authentication

For the hackathon:

- landing page public
- live demonstration dashboard may remain accessible using demo mode

Architect frontend so authentication can be added later.

Do not spend excessive hackathon development time building enterprise RBAC.

---

# 35. Error Handling

Handle:

- malformed telemetry
- unknown station
- missing measurements
- stale readings
- simulator failure
- WebSocket reconnect
- backend unavailable
- map unavailable

UI should show graceful degraded states.

---

# 36. Responsive Design

Must look excellent on:

- desktop projector
- laptop
- tablet
- mobile phone

The `/demo-control` page must be especially good on mobile.

---

# 37. Accessibility

- keyboard navigation
- visible focus states
- semantic HTML
- sensible ARIA labels
- color should not be the only indicator of state
- readable contrast
- reduced-motion support

---

# 38. Performance

Target:

- fast initial landing load
- lazy-load heavy visualization code
- avoid giant image assets
- keep animations GPU-friendly
- avoid constant React rerenders for every telemetry element
- batch or intelligently handle incoming events where appropriate

---

# 39. Security Basics

- validate all telemetry input
- CORS via environment config
- no secrets in frontend
- environment variables
- safe database queries
- rate-limit telemetry endpoint if practical
- reject obviously impossible payloads
- log invalid telemetry separately

---

# 40. Testing

Backend tests:

- telemetry ingestion
- station lookup
- risk calculation
- alert creation
- simulator scenarios
- forecast calculation

Frontend tests for critical state logic where practical.

Include at least one end-to-end smoke flow if time allows:

```text
simulator emits telemetry
→ backend stores reading
→ assessment created
→ WebSocket emits
→ UI updates
```

---

# 41. Docker

Provide:

```text
docker-compose.yml
```

Services:

```text
backend
frontend
database
```

SQLite may be used for simplest local mode.

Also provide non-Docker local instructions.

---

# 42. Environment File

Create `.env.example`.

Example:

```env
DATABASE_URL=
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws/live
CORS_ORIGINS=http://localhost:5173
SIMULATOR_ENABLED=true
SIMULATOR_INTERVAL_SECONDS=3
```

---

# 43. README

README must include:

1. product overview
2. architecture
3. stack
4. setup
5. running frontend
6. running backend
7. starting simulator
8. triggering incidents
9. demo flow
10. Arduino integration
11. limitations
12. future roadmap

---

# 44. Hackathon Demo Script Support

The implementation should support this sequence reliably:

### Scene 1 — Network healthy

Dashboard:

```text
Network Health 94
9 Safe
1 Watch
0 Critical
```

### Scene 2 — trigger contamination

Presenter opens `/demo-control`.

Tap:

```text
CONTAMINATION
```

### Scene 3 — gradual change

Over ~15–25 seconds:

```text
turbidity 2.6
→ 4.2
→ 7.8
→ 11.4
→ 15.1
```

Risk:

```text
12%
→ 28%
→ 52%
→ 74%
→ 89%
```

Status:

```text
SAFE
→ WATCH
→ WARNING
→ CRITICAL
```

### Scene 4 — dashboard reaction

- map node changes
- pulse begins
- alert appears
- chart spike appears
- AI explanation updates

### Scene 5 — prediction

Show:

```text
Tank level: 36%
Forecast:
Critical level likely in 17h 40m
```

### Scene 6 — recovery

Tap:

```text
RECOVER
```

Telemetry gradually normalizes.

---

# 45. Landing/Dashboard Transition

Clicking:

**Open Live Dashboard →**

should feel cinematic.

Possible transition:

- hero network visualization expands
- UI fades into dark operational dashboard
- logo remains temporarily anchored
- route changes

Keep it under ~700 ms.

---

# 46. UI Microcopy

Use confident, restrained product language.

Good:

```text
Telemetry stable
No abnormal patterns detected
Risk increasing
Signal degraded
Verification recommended
Forecast confidence: 82%
```

Avoid:

```text
OMG danger!
Your water is poisoned!
AI has detected bacteria!
```

---

# 47. Prototype Disclaimer

Small but visible where relevant:

> WaterSense AI prototype outputs are decision-support signals based on available telemetry. They do not replace certified laboratory testing or regulatory water-quality assessment.

---

# 48. Definition of Done

Do not consider the task finished unless:

- [ ] Landing page exists and feels polished
- [ ] Landing page has meaningful motion
- [ ] Dashboard is fully implemented
- [ ] Map works
- [ ] Seed stations appear
- [ ] Backend API works
- [ ] Database persists telemetry
- [ ] Simulator continuously generates data
- [ ] Scenario triggers work
- [ ] WebSocket updates dashboard live
- [ ] Risk scores change based on telemetry
- [ ] Isolation Forest or equivalent anomaly model actually runs
- [ ] Alerts are automatically created
- [ ] Station detail charts work
- [ ] Depletion forecast works
- [ ] AI explanation panel works
- [ ] `/demo-control` works on mobile
- [ ] Arduino bridge contract is documented
- [ ] README contains setup/demo instructions
- [ ] Application runs locally from clean setup

---

# 49. Development Priority

If time becomes constrained, implement in this exact order:

```text
P0
Backend skeleton
Database
Telemetry ingestion
Seed data
Simulator

P1
Dashboard overview
Live station updates
Risk engine
Map
Station page

P2
Alerts
Demo-control scenarios
Historical charts
Forecast

P3
AI explanations
Analytics
AI Insights page

P4
Landing page
Advanced animations
Visual polish

P5
Arduino serial bridge
Additional hardware integrations
```

However, the final hackathon build should include both the landing page and dashboard.

---

# 50. Agent Execution Instructions

You are not being asked to merely create a design concept.

**Build the application.**

Work iteratively.

After each major milestone:

1. run the application
2. inspect the output
3. fix console/runtime errors
4. verify API responses
5. verify frontend/backend integration
6. continue

Do not leave obvious placeholder UI.

Do not use lorem ipsum.

Do not silently fake backend behavior inside the frontend.

The simulator may generate synthetic telemetry, but the telemetry must travel through the real backend pipeline.

Prefer maintainable code over hacky single-file implementations.

Do not unnecessarily overengineer enterprise infrastructure.

The final result must be a convincing, functional hackathon prototype that can later accept real Arduino/ESP32 sensor telemetry.

---

# 51. Final Product Feel

When someone opens WaterSense AI, the reaction should be:

> “This looks like infrastructure software that could actually exist.”

The landing page should feel **editorial and experimental**.

The dashboard should feel **calm, precise, operational, and alive**.

The AI should feel **useful and explainable**, not decorative.

The hardware should feel **replaceable and extensible**.

And the demo should tell one clear story:

> **Water infrastructure produces signals before failure. WaterSense AI turns those signals into time to act.**
