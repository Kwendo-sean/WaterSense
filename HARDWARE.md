# WaterSense AI — Hardware Build Plan

What we're building with, how it maps to the telemetry schema, and the build order for the hackathon.

## Kit on hand

Generic Arduino starter kit — Arduino Uno R3/R4, breadboard, jumper wires, prototyping shield, resistors/capacitors/diodes/transistors, 74HC595, L293D, push buttons, 10k potentiometers, photoresistors (LDR), thermistor, DHT11, tilt ball switch, HC-SR04, IR receiver/remote, analog joystick, LEDs + RGB LED, LCD1602, active/passive buzzers, 7-segment displays, SG90 servo, 5V DC motor + fan, stepper + ULN2003, 5V relay.

**No WiFi module, no pH/turbidity/TDS/conductivity/flow probes.** The plan below is built entirely around what's actually in the box — no sensors we don't have.

## Connectivity

The Uno has no network interface, so it **cannot** POST directly to the API. We run the existing bridge script on a laptop, tethered to the Arduino over USB:

```bash
python -m pip install pyserial
python scripts/arduino_serial_bridge.py --port COM4 --baud 9600 \
  --api https://watersense.selenos.world/api/v1/telemetry
```

The bridge (`scripts/arduino_serial_bridge.py`) reads one JSON object per serial line and forwards it, so the sketch just needs:

```cpp
Serial.println("{\"station_code\":\"WS-PROTOTYPE-01\",\"water_level_percent\":64,\"temperature_c\":22.8}");
```

Any subset of these keys is accepted: `ph`, `turbidity_ntu`, `temperature_c`, `conductivity_us_cm`, `tds_ppm`, `water_level_percent`, `flow_rate_l_min`. Baud rate must match `--baud` (default 9600).

Demo rig needs a laptop at the table running the bridge — not a battery-only box across the room. Keep a charged laptop + USB cable as part of the rig checklist.

## Schema field → sensor mapping

| Field | Sensor | Status | Notes |
|---|---|---|---|
| `water_level_percent` | HC-SR04 ultrasonic | Real | Mount above an open container, measure distance to water surface, convert to % using container height. Best sensor in the kit for this — drives the TANK_DEPLETION story and the forecast feature. |
| `temperature_c` | DHT11 (or thermistor) | Real, honest caveat | Reads ambient air near the tank, not a submerged waterproof probe. Fine for a demo — don't claim it's a calibrated water-temp sensor if asked. |
| `turbidity_ntu` | Potentiometer #1 | Manual control, not a sensor | No turbidity sensor in the kit. Wire a pot as a visible "control panel" knob instead of faking a sensor reading — `device.source: "manual"` exists in the schema for exactly this. A presenter turning the knob live is a stronger demo moment than a silent sensor. |
| `conductivity_us_cm` / `tds_ppm` | Potentiometer #2 | Manual control | Same approach. One knob can drive both fields together in the sketch (derive TDS from conductivity or vice versa, like a real probe would). |
| `ph` | Potentiometer #3 | Manual control | Same approach. Only wire this one if time allows — turbidity + water level + temp are the priority three. |
| `flow_rate_l_min` | — | Skipped / optional reverse | No flow sensor in the kit. Leave simulated via `/demo-control`, or optionally drive the DC motor + fan *from* software (spins faster as reported flow increases) as a visual output instead of an input. |

## Physical outputs — hardware reacting to the software's risk state

The backend already computes `risk_level` (`safe`/`watch`/`warning`/`critical`) and a recommended action per station. The bridge laptop can poll `GET /api/v1/stations/{id}` and drive these:

| Output | Behavior |
|---|---|
| RGB LED | Color = risk level (green/yellow/orange/red) |
| Active buzzer | Sounds on `critical` |
| LCD1602 | Station name + current risk score |
| SG90 servo | Rotates to represent a tap/valve closing on `critical` — physical echo of "flag the source, verify before use" |
| 5V relay | Optional, only if cutting power to something adds visual value. Servo covers the "shutoff" story with less risk — skip unless time remains. |

## Build order

1. **HC-SR04 water level** — wire it, confirm a reading reaches the live dashboard through the bridge. Proves the whole chain end-to-end on the most reliable sensor first.
2. **DHT11 temperature**.
3. **One potentiometer → `turbidity_ntu`** (or `ph`, whichever scenario you want to trigger live during the pitch instead of clicking `/demo-control`).
4. **RGB LED + buzzer**, driven by polling station status.
5. **LCD + servo + remaining potentiometers** — polish, only if time remains. Skip under time pressure without regret.

## If a parts run is possible before the event

Not required — the potentiometer-panel plan above is a legitimate fallback — but a cheap analog turbidity or TDS probe (~$5–10 each) would let one of the three "manual knob" fields become a real sensor instead. Lowest priority: `ph` (needs calibration buffers anyway, skip entirely under time pressure).

## Known limitations, stated plainly for judge Q&A

- Temperature is ambient-air, not a submerged probe.
- Turbidity, conductivity/TDS, and pH are operator-controlled inputs, not live chemical sensors, unless upgraded per the parts-run note above.
- Flow rate is simulated, not measured.
- The Arduino requires a USB-tethered laptop running the bridge script; it has no standalone network connection.

None of this is a weakness to hide — the architecture is explicitly sensor-source agnostic (`device.source` supports `simulator` / `arduino` / `esp32` / `manual` / `external` side by side), and the risk engine, forecasting, alerting, and dashboard are identical regardless of where a reading came from. Real sensors can be swapped in field-by-field later without any software changes.
