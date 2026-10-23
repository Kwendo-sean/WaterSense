#!/usr/bin/env python3
"""Forward newline-delimited Arduino JSON to WaterSense.

Expected serial line (non-JSON debug lines are ignored):
  {"station_code":"WS-PROTOTYPE-01","water_level_percent":64,"pump_on":true,"pump_run_ms":1234}
"""
import argparse,json,time,urllib.request
try: import serial
except ImportError: serial=None
METRICS={"ph","turbidity_ntu","temperature_c","conductivity_us_cm","tds_ppm","water_level_percent","flow_rate_l_min"}
DEVICE_FIELDS={"battery_percent","pump_on","pump_run_ms","level_raw","water_contact","motion"}
def normalize(raw):
    return {"station_code":raw["station_code"],"metrics":{k:v for k,v in raw.items() if k in METRICS},
            "device":{"source":"arduino",**{k:v for k,v in raw.items() if k in DEVICE_FIELDS}}}
def forward(url,payload):
    req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={"Content-Type":"application/json"},method="POST")
    with urllib.request.urlopen(req,timeout=10) as response:return json.load(response)
def main():
    p=argparse.ArgumentParser();p.add_argument("--port",required=True);p.add_argument("--baud",type=int,default=9600)
    # Not "localhost": on Windows it tries IPv6 first and stalls ~2 s per request.
    p.add_argument("--api",default="http://127.0.0.1:8000/api/v1/telemetry");args=p.parse_args()
    if serial is None:raise SystemExit("Install pyserial: python -m pip install pyserial")
    waiting=False
    while True:  # survive the board being unplugged or the port being grabbed by the IDE
        try:
            with serial.Serial(args.port,args.baud,timeout=2) as device:
                print(f"{time.strftime('%H:%M:%S')} connected to {args.port}",flush=True);waiting=False
                pump(device,args.api)
        except serial.SerialException as exc:
            if not waiting:print(f"{time.strftime('%H:%M:%S')} {args.port} unavailable ({exc}); retrying every 2 s",flush=True);waiting=True
            time.sleep(2)

def pump(device,api):
    latest=None
    while True:
        line=device.readline().decode("utf-8",errors="replace").strip()
        if line.startswith("{"):latest=line
        # Drain anything already buffered first, so a slow POST never makes
        # the dashboard fall behind the device; only the newest line is sent.
        if device.in_waiting or latest is None:continue
        try:
            result=forward(api,normalize(json.loads(latest)))
            print(f"{time.strftime('%H:%M:%S')} {latest} -> {result.get('station_status')}",flush=True)
        except Exception as exc:print(f"bridge error: {exc}",flush=True);time.sleep(1)
        latest=None
if __name__=="__main__":main()
