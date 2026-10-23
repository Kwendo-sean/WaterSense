import {useEffect,useState} from "react";import {useQuery,useQueryClient} from "@tanstack/react-query";import {WS,api,getAdminKey,setAdminKey,clearAdminKey} from "../api";import type {Status} from "../types";
export function AdminGate({children}:{children:React.ReactNode}){
  const [key,setKey]=useState(()=>getAdminKey());
  const [input,setInput]=useState("");
  const probe=useQuery({queryKey:["admin-probe",key],queryFn:()=>api.simStatus(),enabled:!!key,retry:false});
  function trySubmit(){setAdminKey(input);setKey(input)}
  if(!key||probe.error){
    if(probe.error)clearAdminKey();
    return <main className="survey-admin-gate"><Logo dark/><h1>Operator access</h1><p>Enter the operator password to view the dashboard.</p>{probe.error&&<p className="survey-error">Access denied — check the password and try again.</p>}<input type="password" value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>e.key==="Enter"&&trySubmit()} placeholder="Password"/><button onClick={trySubmit}>Continue</button></main>;
  }
  if(probe.isLoading)return <div className="survey-admin"><Loading/></div>;
  return <>{children}</>;
}
export function Logo({dark=false}:{dark?:boolean}){return <div className={`logo ${dark?"logo-dark":""}`}><span className="drop-mark">◒</span><span>WATERSENSE <b>AI</b></span></div>}
export function StatusPill({status}:{status:Status|string}){return <span className={`status status-${status}`}><i/>{status.toUpperCase()}</span>}
// Server-computed views (totals, lists, charts) refetched at most this often.
const AGGREGATE_KEYS=["summary","stations","activity","alerts","pumps","pump","risk","forecast"];
const AGGREGATE_EVERY_MS=1000;
const HISTORY_CACHES:[string,number][]=[["",100],["hw",300]];

export function LiveSocket(){
  const qc=useQueryClient();const [connected,setConnected]=useState(false);
  useEffect(()=>{
    let ws:WebSocket|undefined,retry:number|undefined,pending:number|undefined,last=0,disposed=false;
    const refreshAggregates=()=>{pending=undefined;last=Date.now();AGGREGATE_KEYS.forEach(k=>qc.invalidateQueries({queryKey:[k]}))};
    // Leading + trailing throttle: an update lands immediately, a burst still ends with a final refresh.
    const scheduleAggregates=()=>{if(pending===undefined)pending=window.setTimeout(refreshAggregates,Math.max(0,AGGREGATE_EVERY_MS-(Date.now()-last)))};
    // The push already carries the full reading, so write it straight into the
    // cache: the page updates instantly without a single extra request.
    const applyReading=(d:any)=>{
      const id=d.station.id;
      qc.setQueryData(["latest",id],{station:d.station,reading:d.reading,risk:d.risk});
      for(const [suffix,keep] of HISTORY_CACHES){
        const key=suffix?["telemetry",id,suffix]:["telemetry",id];
        qc.setQueryData(key,(old:any[]|undefined)=>old?[...old.filter(r=>r.id!==d.reading.id),d.reading].slice(-keep):old);
      }
    };
    const open=()=>{
      const key=getAdminKey();
      ws=new WebSocket(WS+(key?`?key=${encodeURIComponent(key)}`:""));
      ws.onopen=()=>{setConnected(true);refreshAggregates()};
      ws.onclose=()=>{setConnected(false);if(!disposed)retry=window.setTimeout(open,2000)};
      ws.onmessage=(e)=>{
        let m:any;try{m=JSON.parse(e.data)}catch{return}
        if(m.event==="telemetry:new")applyReading(m.data);
        if(m.event==="pump:changed")qc.invalidateQueries({queryKey:["pump",m.data.station_id]});
        scheduleAggregates();
      };
    };
    open();
    return()=>{disposed=true;clearTimeout(retry);clearTimeout(pending);ws?.close()};
  },[qc]);
  return <span className={`connection ${connected?"online":""}`}><i/>{connected?"LIVE LINK":"RECONNECTING"}</span>;
}
export function Loading({label="Synchronizing telemetry"}:{label?:string}){return <div className="loading"><span/><p>{label}</p></div>}
export function ErrorState({message="Backend unavailable"}:{message?:string}){return <div className="error-state"><strong>SIGNAL INTERRUPTED</strong><p>{message}. WaterSense will reconnect automatically.</p></div>}
export function Disclaimer(){return <p className="disclaimer">WaterSense AI prototype outputs are decision-support signals based on available telemetry. They do not replace certified laboratory testing or regulatory water-quality assessment.</p>}
export const fmt=(v:number|null|undefined,d=1)=>v==null?"—":v.toFixed(d);
