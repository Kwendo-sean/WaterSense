#!/usr/bin/env python3
"""Normalize newline-delimited Arduino JSON and forward it to WaterSense.

Expected serial line:
  {"station_code":"WS-PROTOTYPE-01","ph":7.08,"turbidity_ntu":3.1,"water_level_percent":64}
"""
import argparse,json,time,urllib.request
try: import serial
except ImportError: serial=None
METRICS={"ph","turbidity_ntu","temperature_c","conductivity_us_cm","tds_ppm","water_level_percent","flow_rate_l_min"}
def normalize(raw):
    return {"station_code":raw["station_code"],"metrics":{k:v for k,v in raw.items() if k in METRICS},"device":{"source":"arduino","battery_percent":raw.get("battery_percent")}}
def forward(url,payload):
    req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={"Content-Type":"application/json"},method="POST")
    with urllib.request.urlopen(req,timeout=10) as response:return json.load(response)
def main():
    p=argparse.ArgumentParser();p.add_argument("--port",required=True);p.add_argument("--baud",type=int,default=9600);p.add_argument("--api",default="http://localhost:8000/api/v1/telemetry");args=p.parse_args()
    if serial is None:raise SystemExit("Install pyserial: python -m pip install pyserial")
    with serial.Serial(args.port,args.baud,timeout=2) as device:
        while True:
            try:
                line=device.readline().decode("utf-8",errors="replace").strip()
                if line:print(forward(args.api,normalize(json.loads(line))))
            except Exception as exc:print(f"bridge error: {exc}");time.sleep(1)
if __name__=="__main__":main()
