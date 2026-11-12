import {useState} from "react";
import {keepPreviousData,useQuery} from "@tanstack/react-query";
import {ChevronDown,History} from "lucide-react";
import {api} from "../api";
import {fmt} from "./Shared";

// Every finding WaterSense AI raised for this station, as episodes: when it was
// first flagged, the evidence then and now, and when it cleared.
const RANGES:[string,number][]=[["6H",6],["24H",24],["7D",168]];
const FILTERS:[string,(i:any)=>boolean][]=[["ALL",()=>true],["ACTIVE",i=>i.active],["CRITICAL",i=>i.severity==="critical"],["WARNING",i=>i.severity==="warning"]];

function span(s:number){
  if(s<60)return `${s}s`;
  if(s<3600)return `${Math.floor(s/60)}m ${String(s%60).padStart(2,"0")}s`;
  const h=Math.floor(s/3600);return h<48?`${h}h ${Math.floor(s%3600/60)}m`:`${Math.floor(h/24)}d ${h%24}h`;
}
function when(ts:string){
  const d=new Date(ts),today=new Date().toDateString()===d.toDateString();
  return d.toLocaleString([],{...(today?{}:{month:"short",day:"numeric"}),hour:"2-digit",minute:"2-digit",second:"2-digit"});
}
function ago(ts:string){return span(Math.max(0,Math.round((Date.now()-new Date(ts).getTime())/1000)))+" ago"}

const CONTEXT:[string,string,(v:any)=>string][]=[
  ["level_percent","Level",v=>`${fmt(v,0)}%`],
  ["liters_in_tank","In tank",v=>`${fmt(v,1)} L`],
  ["pump_on","Pump",v=>v?"Running":"Off"],
  ["level_rate_per_min","Level trend",v=>`${v>0?"+":""}${fmt(v,2)} %/min`],
  ["current_cycle_minutes","Cycle so far",v=>`${fmt(v,1)} min`],
  ["pump_starts_1h","Starts / hour",v=>String(v)],
  ["duty_cycle_percent_1h","Pump duty 1 h",v=>`${fmt(v,0)}%`],
  ["water_contact","Base sensor",v=>v?"Wet":"Dry"],
];

function Timeline({items,hours}:{items:any[];hours:number}){
  const end=Date.now(),start=end-hours*3600e3;
  const titles=[...new Set(items.map(i=>i.title))];
  const pos=(ts:string)=>Math.min(100,Math.max(0,(new Date(ts).getTime()-start)/(end-start)*100));
  return <div className="fh-timeline">
    {titles.map(t=><div className="fh-lane" key={t}>
      <span title={t}>{t}</span>
      <div>{items.filter(i=>i.title===t).map(i=>{
        const l=pos(i.first_seen),r=i.active?100:pos(i.resolved_at||i.last_seen);
        return <i key={i.id} className={`${i.severity} ${i.active?"active":""}`} style={{left:`${l}%`,width:`max(3px,${r-l}%)`}} title={`${when(i.first_seen)} · ${span(i.duration_seconds)}`}/>;
      })}</div>
    </div>)}
    <div className="fh-axis"><span>{hours<=24?`${hours} h ago`:`${hours/24} days ago`}</span><span>now</span></div>
  </div>;
}

export default function FindingHistory({id}:{id:number}){
  const [hours,setHours]=useState(24);
  const [filter,setFilter]=useState("ALL");
  const [open,setOpen]=useState<number|null>(null);
  const q=useQuery({queryKey:["insights-history",id,hours],queryFn:()=>api.insightsHistory(id,hours),refetchInterval:10000,placeholderData:keepPreviousData});
  const data=q.data;
  const items=(data?.items||[]).filter((FILTERS.find(([k])=>k===filter)||FILTERS[0])[1]);

  return <section className="finding-history">
    <div className="fh-head">
      <div className="pump-head"><History/><span>AI FINDING HISTORY</span></div>
      <div className="timeframes">{RANGES.map(([label,h])=><button key={label} className={hours===h?"active":""} onClick={()=>setHours(h)}>{label}</button>)}</div>
    </div>

    {!data?<p className="pump-empty">Loading finding history…</p>:data.total===0?
      <p className="pump-empty">No findings in the last {hours<=24?`${hours} hours`:`${hours/24} days`}. History builds up while the device is reporting: the analysis runs every 10 seconds and logs anything it flags here.</p>:<>
      <div className="fh-stats">
        <div><span>EPISODES</span><b>{data.total}</b></div>
        <div className={data.active?"live":""}><span>ACTIVE NOW</span><b>{data.active}</b></div>
        <div><span>CRITICAL</span><b>{data.items.filter((i:any)=>i.severity==="critical").length}</b></div>
        <div><span>MOST FREQUENT</span><b className="small">{data.by_title[0]?.title||"—"}</b></div>
      </div>

      <div className="fh-summary">{data.by_title.map((t:any)=><div key={t.title} className={t.severity}>
        <b>{t.title}</b><span>{t.episodes}× · {span(t.total_seconds)} total · last {ago(t.last_seen)}</span>
      </div>)}</div>

      <Timeline items={data.items} hours={hours}/>

      <div className="fh-filters">{FILTERS.map(([k])=><button key={k} className={filter===k?"active":""} onClick={()=>setFilter(k)}>{k}</button>)}</div>

      <ol className="fh-list">
        {items.map((i:any)=><li key={i.id} className={`${i.severity} ${open===i.id?"open":""}`}>
          <button onClick={()=>setOpen(open===i.id?null:i.id)}>
            <em className={i.active?"active":""}>{i.active?"ACTIVE":"CLEARED"}</em>
            <b>{i.title}</b>
            <time>{when(i.first_seen)} → {i.active?"now":when(i.resolved_at)}</time>
            <span>{span(i.duration_seconds)}</span>
            <ChevronDown/>
          </button>
          {open===i.id&&<div className="fh-detail">
            <div><h4>When first raised · {when(i.first_seen)}</h4><p>{i.first_detail}</p></div>
            {i.last_detail!==i.first_detail&&<div><h4>Latest evidence · {when(i.last_seen)}</h4><p>{i.last_detail}</p></div>}
            {i.context?.headline&&<div><h4>Tank state at the time</h4><p>{i.context.headline}</p></div>}
            <div className="fh-context">{CONTEXT.filter(([k])=>i.context?.[k]!=null).map(([k,label,f])=><div key={k}><span>{label}</span><b>{f(i.context[k])}</b></div>)}</div>
            {i.action&&<div><h4>Recommended at the time</h4><p>{i.action}</p></div>}
            <p className="fh-meta">Confirmed by {i.checks} analysis run{i.checks===1?"":"s"} · {i.active?`still present, last checked ${ago(i.last_seen)}`:`cleared ${when(i.resolved_at)}`}</p>
          </div>}
        </li>)}
        {!items.length&&<p className="pump-empty">Nothing matches this filter.</p>}
      </ol>
    </>}
  </section>;
}
