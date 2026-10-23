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
export function LiveSocket(){const qc=useQueryClient();const [connected,setConnected]=useState(false);useEffect(()=>{let ws:WebSocket|undefined;let retry:number;let refresh:number|undefined;const invalidate=()=>{qc.invalidateQueries({queryKey:["summary"]});qc.invalidateQueries({queryKey:["stations"]});qc.invalidateQueries({queryKey:["activity"]});qc.invalidateQueries({queryKey:["alerts"]});qc.invalidateQueries({queryKey:["latest"]});qc.invalidateQueries({queryKey:["telemetry"]});qc.invalidateQueries({queryKey:["risk"]});qc.invalidateQueries({queryKey:["pumps"]});qc.invalidateQueries({queryKey:["pump"]})};const open=()=>{const key=getAdminKey();ws=new WebSocket(WS+(key?`?key=${encodeURIComponent(key)}`:""));ws.onopen=()=>setConnected(true);ws.onclose=()=>{setConnected(false);retry=window.setTimeout(open,2000)};
    // Leading-edge throttle, not a debounce: a continuous fast stream (a real
    // device posting every ~500ms) must not starve the UI update by endlessly
    // pushing a trailing timer back. Fire once immediately, then at most every
    // 150ms while messages keep arriving, instead of waiting for silence.
    ws.onmessage=()=>{if(refresh===undefined){invalidate();refresh=window.setTimeout(()=>{refresh=undefined},150)}}};open();return()=>{clearTimeout(retry);clearTimeout(refresh);ws?.close()}},[qc]);return <span className={`connection ${connected?"online":""}`}><i/>{connected?"LIVE LINK":"RECONNECTING"}</span>}
export function Loading({label="Synchronizing telemetry"}:{label?:string}){return <div className="loading"><span/><p>{label}</p></div>}
export function ErrorState({message="Backend unavailable"}:{message?:string}){return <div className="error-state"><strong>SIGNAL INTERRUPTED</strong><p>{message}. WaterSense will reconnect automatically.</p></div>}
export function Disclaimer(){return <p className="disclaimer">WaterSense AI prototype outputs are decision-support signals based on available telemetry. They do not replace certified laboratory testing or regulatory water-quality assessment.</p>}
export const fmt=(v:number|null|undefined,d=1)=>v==null?"—":v.toFixed(d);
