import {useEffect,useState} from "react";
import {Link} from "react-router-dom";
import {keepPreviousData,useMutation,useQuery,useQueryClient} from "@tanstack/react-query";
import {Area,AreaChart,CartesianGrid,ReferenceLine,ResponsiveContainer,Tooltip,XAxis,YAxis} from "recharts";
import {ArrowLeft,BrainCircuit,CalendarClock,Clock,Droplet,Maximize2,Minimize2,Power,Radio,ShieldAlert,X} from "lucide-react";
import {api} from "../api";
import {Disclaimer,fmt,LiveSocket,Logo} from "../components/Shared";
import FindingHistory from "../components/FindingHistory";

const START_PERCENT=20, STOP_PERCENT=85;
const STATUS_PILL:Record<string,[string,string]>={normal:["safe","NORMAL"],attention:["warning","ATTENTION"],fault:["critical","FAULT"],offline:["watch","OFFLINE"],no_data:["watch","NO DATA"]};
// One-character commands the controller obeys (see backend services/pump_control.py).
const COMMAND_LABEL:Record<string,string>={A:"AUTOMATIC",1:"MANUAL ON",0:"MANUAL OFF",S:"SCHEDULED RUN"};

function inMinutes(n:number){const d=new Date(Date.now()+n*60000);return `${String(d.getHours()).padStart(2,"0")}:${String(d.getMinutes()).padStart(2,"0")}`}

const MAX_SCHEDULE_DAYS=31;  // matches SCHEDULE_MAX_DAYS on the backend
function localDate(offsetDays:number){const d=new Date(Date.now()+offsetDays*86400000);return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`}
function PumpControls({id,reading}:{id:number;reading:any}){
  const qc=useQueryClient();
  const control=useQuery({queryKey:["pumpControl",id],queryFn:()=>api.pumpControl(id),refetchInterval:15000});
  const apply=(state:any)=>qc.setQueryData(["pumpControl",id],state);
  const setMode=useMutation({mutationFn:(mode:string)=>api.setPumpMode(id,mode),onSuccess:apply});
  const addSchedule=useMutation({mutationFn:(body:any)=>api.addPumpSchedule(id,body),onSuccess:apply});
  const removeSchedule=useMutation({mutationFn:(sid:number)=>api.deletePumpSchedule(id,sid),onSuccess:apply});
  const [start,setStart]=useState(()=>inMinutes(1));
  const [minutes,setMinutes]=useState(5);
  const [repeat,setRepeat]=useState("once");
  const [day,setDay]=useState(()=>localDate(0));

  const c=control.data;
  const mode=c?.mode??"auto";
  const confirmed=c&&reading.pump_mode===c.command;
  const error=setMode.error||addSchedule.error||removeSchedule.error;
  return <div className="pump-control">
    <div className="pump-control-row">
      <span className="pump-control-label">PUMP MODE</span>
      <div className="seg" role="group" aria-label="Pump mode">
        {[["auto","AUTO"],["on","ON"],["off","OFF"]].map(([m,label])=><button key={m} className={mode===m?`active ${m}`:""} disabled={setMode.isPending} onClick={()=>setMode.mutate(m)}>{label}</button>)}
      </div>
      <p className="pump-control-state">
        {c?<>Sending <b>{COMMAND_LABEL[c.command]}</b>{c.active_schedule&&` until ${clock(c.active_schedule.ends_at,false)}`} · {confirmed?<em className="ok">device confirmed</em>:<em>waiting for the device…</em>}</>:"Loading…"}
      </p>
    </div>
    <p className="pump-control-hint">{mode==="on"?"Manual ON fills the tank and hands back to AUTO when it reaches 100%.":mode==="off"?"Manual OFF holds the motor off, even if the tank runs low or a schedule is due.":"AUTO runs the motor at ≤20% and stops it at ≥85%. Schedules below run on top of this."}</p>

    <form className="pump-schedule-form" onSubmit={e=>{e.preventDefault();addSchedule.mutate({start_time:start,duration_minutes:minutes,repeat,...(repeat==="once"?{run_date:day}:{})})}}>
      <span className="pump-control-label"><CalendarClock/> SCHEDULE A RUN</span>
      {repeat==="once"&&<label>DATE<input type="date" required min={localDate(0)} max={localDate(MAX_SCHEDULE_DAYS)} value={day} onChange={e=>setDay(e.target.value)}/></label>}
      <label>START<input type="time" required value={start} onChange={e=>setStart(e.target.value)}/></label>
      <label>FOR<input type="number" min={1} max={720} required value={minutes} onChange={e=>setMinutes(Number(e.target.value))}/><small>min</small></label>
      <label>REPEAT<select value={repeat} onChange={e=>setRepeat(e.target.value)}><option value="once">Once</option><option value="daily">Every day</option></select></label>
      <button type="submit" disabled={addSchedule.isPending}>ADD</button>
    </form>
    {c?.schedules?.length>0&&<div className="pump-schedules">
      {c.schedules.map((s:any)=><div key={s.id} className={s.running?"running":""}>
        <b>{s.start_time}</b><span>{s.duration_minutes} min · {s.repeat==="daily"?"every day":s.run_date?`once · ${new Date(`${s.run_date}T00:00`).toLocaleDateString([],{weekday:"short",day:"numeric",month:"short"})}`:"once"}</span>
        <em>{s.running?"RUNNING NOW":s.next_run?`next ${new Date(s.next_run).toLocaleString([],{weekday:"short",day:"numeric",month:"short",hour:"2-digit",minute:"2-digit"})}`:""}</em>
        <button aria-label="Delete schedule" onClick={()=>removeSchedule.mutate(s.id)}><X/></button>
      </div>)}
    </div>}
    {error&&<p className="pump-control-error">{(error as Error).message}</p>}
  </div>;
}

function duration(ms:number){
  const s=Math.max(0,Math.round(ms/1000));
  if(s<60)return `${s}s`;
  const m=Math.floor(s/60);
  return m<60?`${m}m ${String(s%60).padStart(2,"0")}s`:`${Math.floor(m/60)}h ${m%60}m`;
}
function clock(ts:string,seconds=true){return new Date(ts).toLocaleTimeString([],{hour:"2-digit",minute:"2-digit",...(seconds?{second:"2-digit"}:{})})}
function sparkPath(vals:number[]){
  const w=160,h=30,pad=3;
  if(vals.length<2)return `M${pad} ${h/2} L${w-pad} ${h/2}`;
  const min=Math.min(...vals),max=Math.max(...vals),range=max-min||1,step=(w-2*pad)/(vals.length-1);
  return vals.map((v,i)=>`${i===0?"M":"L"}${(pad+i*step).toFixed(1)} ${(pad+(h-2*pad)*(1-(v-min)/range)).toFixed(1)}`).join(" ");
}

// Panel overlay rather than the browser Fullscreen API: works the same in every
// browser and keeps the live socket and dark theme around it.
function useFullscreen():[boolean,()=>void]{
  const [on,setOn]=useState(false);
  useEffect(()=>{
    if(!on)return;
    const onKey=(e:KeyboardEvent)=>{if(e.key==="Escape")setOn(false)};
    window.addEventListener("keydown",onKey);document.body.style.overflow="hidden";
    return()=>{window.removeEventListener("keydown",onKey);document.body.style.overflow=""};
  },[on]);
  return [on,()=>setOn(v=>!v)];
}
function FullscreenButton({on,toggle}:{on:boolean;toggle:()=>void}){
  return <button className="fs-btn" onClick={toggle} aria-label={on?"Exit full screen":"Full screen"} title={on?"Exit full screen (Esc)":"Full screen"}>{on?<Minimize2/>:<Maximize2/>}</button>;
}

function nextRunLabel(p:any){
  if(!p?.next_run_at)return "—";
  const at=new Date(p.next_run_at),now=new Date();
  const time=at.toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"});
  return `${at.toDateString()===now.toDateString()?"Today":"Tomorrow"} ~${time}`;
}

const AI_METRICS:[string,string,(v:any)=>string][]=[
  ["level_rate_per_min","LEVEL CHANGE",v=>`${v>0?"+":""}${fmt(v,2)} %/min`],
  ["minutes_to_full","TIME TO FULL",v=>`${fmt(v,1)} min`],
  ["minutes_to_pump_start","TIME TO PUMP START",v=>`${fmt(v,1)} min`],
  ["current_cycle_liters","THIS CYCLE",v=>`${fmt(v,1)} L`],
  ["pumped_24h_liters","PUMPED 24 H",v=>`${fmt(v,0)} L`],
  ["cycles_24h","CYCLES 24 H",v=>String(v)],
  ["pump_starts_1h","STARTS LAST HOUR",v=>String(v)],
  ["duty_cycle_percent_1h","PUMP DUTY 1 H",v=>`${fmt(v,0)}%`],
  ["last_seen_seconds","LAST READING",v=>`${fmt(v,0)} s ago`],
];
function AiMetrics({m}:{m:any}){
  return <div className="ai-metrics">{AI_METRICS.map(([k,label,f])=><div key={k}><span>{label}</span><b>{m?.[k]==null?"—":f(m[k])}</b></div>)}</div>;
}

const RANGES:[string,number][]=[["LIVE",0],["1H",60],["6H",360],["24H",1440],["7D",10080]];
function bucketLabel(s:number){return s<60?`${s}-SECOND`:s<3600?`${Math.round(s/60)}-MINUTE`:`${Math.round(s/3600)}-HOUR`}

function LevelChart({id,rows,hasPump}:{id:number;rows:any[];hasPump:boolean}){
  const [minutes,setMinutes]=useState(0);
  const [full,toggleFull]=useFullscreen();
  const series=useQuery({queryKey:["series",id,minutes],queryFn:()=>api.series(id,minutes),enabled:minutes>0,
    refetchInterval:minutes<=60?5000:30000,placeholderData:keepPreviousData});
  const live=minutes===0;
  const multiDay=minutes>1440;
  const data=live
    ?rows.map((r:any)=>({time:clock(r.timestamp),level:r.water_level_percent,pump:r.pump_on?100:0}))
    :(series.data?.points||[]).map((p:any)=>({time:multiDay?new Date(p.t).toLocaleString([],{weekday:"short",hour:"2-digit",minute:"2-digit"}):clock(p.t,false),level:p.level,band:[p.min,p.max],pump:Math.round(p.pump*100)}));
  const caption=live?`LIVE · LAST ${rows.length} READINGS`:series.data?`LAST ${RANGES.find(r=>r[1]===minutes)![0].replace("H"," HOURS").replace("D"," DAYS")} · ${bucketLabel(series.data.bucket_seconds)} AVERAGES`:"LOADING HISTORY…";
  return <section className={`panel history-panel ${full?"is-fullscreen":""}`}>
    <div className="panel-head">
      <div><span>{caption}</span><h2>{hasPump?"Tank level and pump activity":"Tank level"}</h2></div>
      <div className="chart-tools">
        <div className="seg small" role="group" aria-label="Time range">{RANGES.map(([label,m])=><button key={label} className={minutes===m?"active":""} onClick={()=>setMinutes(m)}>{label}</button>)}</div>
        <FullscreenButton on={full} toggle={toggleFull}/>
      </div>
    </div>
    <div className="chart-body">
      {!live&&series.data&&!data.length?<p className="pump-empty">No readings in this period.</p>:
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data}>
          <defs><linearGradient id="lvl" x1="0" y1="0" x2="0" y2="1"><stop stopColor="#23d5e7" stopOpacity=".35"/><stop offset="1" stopColor="#23d5e7" stopOpacity="0"/></linearGradient></defs>
          <CartesianGrid stroke="#17313a" vertical={false}/>
          <XAxis dataKey="time" stroke="#68838c" minTickGap={50}/>
          <YAxis domain={[0,100]} stroke="#68838c" unit="%"/>
          <Tooltip contentStyle={{background:"#071b23",border:"1px solid #25414a"}} formatter={(v:any,n:any)=>
            n==="Pump"?[live?(v?"ON":"OFF"):`ran ${v}% of the time`,n]:n==="Range"?[`${v[0]}% – ${v[1]}%`,n]:[`${v}%`,n]}/>
          {hasPump&&<Area type="stepAfter" dataKey="pump" stroke="none" fill="#55e68a" fillOpacity={.12} name="Pump" isAnimationActive={false}/>}
          {!live&&<Area type="monotone" dataKey="band" stroke="none" fill="#23d5e7" fillOpacity={.12} name="Range" isAnimationActive={false}/>}
          <Area type="monotone" dataKey="level" stroke="#23d5e7" fill={live?"url(#lvl)":"none"} name="Level" isAnimationActive={false} dot={false}/>
          {hasPump&&<ReferenceLine y={STOP_PERCENT} stroke="#55e68a" strokeDasharray="4 4" label={{value:`STOP ${STOP_PERCENT}%`,fill:"#55e68a",fontSize:9,position:"insideTopRight"}}/>}
          {hasPump&&<ReferenceLine y={START_PERCENT} stroke="#ffb547" strokeDasharray="4 4" label={{value:`START ${START_PERCENT}%`,fill:"#ffb547",fontSize:9,position:"insideBottomRight"}}/>}
        </AreaChart>
      </ResponsiveContainer>}
    </div>
    <div className="chart-key"><span><i className="cyan"/>{live?"Tank level":"Average level (shaded: low–high)"}</span>{hasPump&&<><span><i className="green"/>{live?"Pump running":"Share of time the pump ran"}</span><span>Dashed lines: automatic start / stop points</span></>}</div>
  </section>;
}

export default function HardwareStation({id,station,reading}:{id:number;station:any;reading:any}){
  const history=useQuery({queryKey:["telemetry",id,"hw"],queryFn:()=>api.telemetry(id,300)});
  const pump=useQuery({queryKey:["pump",id],queryFn:()=>api.pump(id)});
  // Recomputed server-side over the last hour of readings, so poll it rather than refetch on every push.
  const insights=useQuery({queryKey:["insights",id],queryFn:()=>api.insights(id),refetchInterval:1500});

  const rows=(history.data||[]).filter((r:any)=>r.source==="arduino"||r.source==="esp32");
  // The ESP32 rig reports sensors only until a pump is wired to it.
  const esp32=reading.source==="esp32";
  const hasPump=!esp32||reading.pump_on!=null;
  const level=reading.water_level_percent??0;
  const capacity=station.pump_capacity_liters;
  const pumpOn=reading.pump_on??station.pump_status==="on";
  const cycle=pump.data?.current_cycle;
  const cycleMs=cycle?Date.now()-new Date(cycle.triggered_at).getTime():0;
  const ai=insights.data;
  const [pillClass,pillLabel]=STATUS_PILL[ai?.status]||["watch","ANALYSING"];
  const prediction=pump.data?.prediction;
  const today=pump.data?.today;
  const daily=pump.data?.daily||[];
  const dailyMax=Math.max(1,...daily.map((d:any)=>d.volume_liters));
  const [aiFull,toggleAiFull]=useFullscreen();
  const levelSeries=rows.map((r:any)=>r.water_level_percent).filter((v:any)=>v!=null).slice(-60);

  return <main className="station-page">
    <nav className="station-nav"><Link to="/dashboard/stations"><ArrowLeft/> Back to network</Link><Logo dark/><LiveSocket/></nav>

    <header className="station-hero">
      <div>
        <span>{station.station_code} · <i>LIVE HARDWARE</i></span>
        <h1>{station.name}</h1>
        <p>{station.location_text} / {!esp32?"ARDUINO UNO · AUTOMATIC PUMP CONTROLLER":hasPump?`ESP32-S3 · AUTOMATIC PUMP CONTROLLER · RELAY + MINI PUMP${reading.level_simulated?" · LEVEL RISE SIMULATED WHILE PUMPING":""}`:"ESP32-S3 · LEVEL AND FLOW SENSORS"}</p>
      </div>
      <div className={`station-risk ${pillClass}`}>
        <span className={`status status-${pillClass}`}><i/>{pillLabel}</span>
        <strong>{reading.water_level_percent==null?"—":fmt(level,0)}<small>%</small></strong>
        <span>TANK LEVEL</span>
        <p><Clock/> UPDATED {clock(reading.timestamp)}</p>
      </div>
    </header>

    {!hasPump&&<section className="telemetry-blocks hw-sensors">
      <div className="telemetry-block"><span>WATER LEVEL</span><div><b>{reading.water_level_percent==null?"—":fmt(level,0)}</b><small>%</small></div><svg viewBox="0 0 160 30"><path d={sparkPath(levelSeries)}/></svg><p className="hw-sub">{reading.water_level_percent==null?"no echo from the sensor":"JSN-SR04T ultrasonic"}</p></div>
      <div className="telemetry-block"><span>DISTANCE TO WATER</span><div><b>{reading.distance_cm==null?"—":fmt(reading.distance_cm,1)}</b><small>cm</small></div><p className="hw-sub">probe to water surface</p></div>
      <div className={`telemetry-block hw-pump ${reading.flow_rate_l_min>0?"on":""}`}><span>FLOW RATE</span><div><b>{fmt(reading.flow_rate_l_min,1)}</b><small>L/min</small></div><p className="hw-sub">YF-S201 flow sensor</p></div>
      <div className="telemetry-block"><span>TOTAL FLOW</span><div><b>{fmt(reading.flow_total_liters,2)}</b><small>L</small></div><p className="hw-sub">since the board restarted</p></div>
    </section>}

    {hasPump&&<section className="telemetry-blocks hw-sensors">
      <div className="telemetry-block"><span>WATER LEVEL</span><div><b>{fmt(level,0)}</b><small>%</small></div><svg viewBox="0 0 160 30"><path d={sparkPath(levelSeries)}/></svg><p><i/> {esp32?`${reading.level_simulated?"SIMULATED FILL · sensor ":""}${reading.distance_cm==null?"NO ECHO":`${fmt(reading.distance_cm,1)} CM TO WATER`}`:`RAW ADC ${reading.level_raw??"—"}`}</p></div>
      <div className="telemetry-block"><span>WATER IN TANK</span><div><b>{Math.round(level/100*capacity).toLocaleString()}</b><small>L</small></div><p className="hw-sub">of {capacity.toLocaleString()} L capacity</p></div>
      <div className={`telemetry-block hw-pump ${pumpOn?"on":""}`}><span>PUMP MOTOR</span><div><b>{pumpOn?"ON":"OFF"}</b></div><p className="hw-sub">{pumpOn?`running ${duration(cycleMs)}`:reading.pump_mode==="0"?"held off from dashboard":`starts at ≤${START_PERCENT}%`}</p></div>
      <div className={`telemetry-block ${reading.water_contact?"hw-alert":""}`}><span>WATER CONTACT</span><div><b>{reading.water_contact==null?"—":reading.water_contact?"WET":"DRY"}</b></div><p className="hw-sub">base leak sensor</p></div>
      {esp32
        ?<div className={`telemetry-block hw-pump ${reading.flow_rate_l_min>0?"on":""}`}><span>WATER FLOW</span><div><b>{fmt(reading.flow_rate_l_min,1)}</b><small>L/min</small></div><p className="hw-sub">YF-S201 · {fmt(reading.flow_total_liters,2)} L since restart</p></div>
        :<div className="telemetry-block"><span>MOTION</span><div><b>{reading.motion==null?"—":reading.motion?"YES":"NONE"}</b></div><p className="hw-sub">{reading.motion==null?"PIR warming up":"PIR sensor"}</p></div>}
    </section>}

    {hasPump&&<section className="pump-panel lead">
      <div className="pump-head"><Droplet/><span>PUMP CONTROL</span></div>
      <div className="pump-top">
        <div className={`pump-indicator ${pumpOn?"on":"off"}`}><Power/>{pumpOn?"PUMPING NOW":"IDLE"}</div>
        <p>While the motor runs, inflow is simulated at 1% of the tank every 3 s (≈{fmt(pump.data?.flow_rate_lpm,0)} L/min into {capacity.toLocaleString()} L), and turning the knob still sets the level directly. Volume is metered from the motor's run time at that rate.</p>
      </div>
      <PumpControls id={id} reading={reading}/>
      <div className="pump-prediction">
        <div><span>THIS CYCLE</span><b>{cycle?`${fmt(cycle.volume_liters,1)} L`:"—"}</b></div>
        <div><span>PUMPED TODAY</span><b>{fmt(today?.volume_liters??0,1)} L</b></div>
        <div><span>CYCLES TODAY</span><b>{today?.cycles??0}</b></div>
        <div><span>NEXT LIKELY RUN</span><b>{nextRunLabel(prediction)}</b></div>
      </div>
      {prediction?<p className="pump-empty">Usually starts around {String(prediction.predicted_hour).padStart(2,"0")}:00 (seen on {prediction.days_at_hour} of {prediction.days_observed} day{prediction.days_observed===1?"":"s"}) · averages {fmt(prediction.avg_daily_volume_liters,0)} L and {fmt(prediction.avg_daily_cycles,1)} cycles a day · confidence {fmt(prediction.confidence,0)}%</p>
        :<p className="pump-empty">The daily prediction appears once a pump cycle has moved water.</p>}
      {daily.length>0&&<div className="pump-daily" aria-label="Water pumped per day, last 7 days">
        {daily.map((d:any,i:number)=><div key={d.date} className={i===daily.length-1?"today":""} title={`${d.cycles} cycle${d.cycles===1?"":"s"}`}>
          <b>{d.volume_liters>0?`${fmt(d.volume_liters,0)} L`:"—"}</b>
          <i style={{height:Math.max(3,d.volume_liters/dailyMax*70)}}/>
          <span>{i===daily.length-1?"TODAY":new Date(d.date+"T12:00").toLocaleDateString([],{weekday:"short"}).toUpperCase()}</span>
        </div>)}
      </div>}
      {pump.data?.recent_events?.length>0&&<div className="pump-history"><span>RECENT CYCLES</span>{pump.data.recent_events.slice(0,6).map((e:any)=><div key={e.id}><time>{new Date(e.triggered_at).toLocaleString([],{month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"})}</time><b>{fmt(e.volume_liters,1)} L</b><time>{fmt(e.trigger_level,0)}% → {fmt(e.stop_level,0)}%</time></div>)}</div>}
    </section>}

    <div className="station-grid">
      <LevelChart id={id} rows={rows} hasPump={hasPump}/>

      <section className={`ai-panel ${pillClass} ${aiFull?"is-fullscreen":""}`}>
        <div className="ai-title"><BrainCircuit/><span>WATERSENSE AI · {hasPump?"TANK & PUMP":"TANK & FLOW"}</span><FullscreenButton on={aiFull} toggle={toggleAiFull}/></div>
        <span className={`status status-${pillClass}`}><i/>{pillLabel}</span>
        {ai?<div className="ai-body">
          <div>
            <h2 className="ai-headline">{ai.headline}</h2>
            <p>{ai.summary}</p>
            <aside><ShieldAlert/><div><h3>Recommended action</h3><p>{ai.recommended_action}</p></div></aside>
            {aiFull&&<AiMetrics m={ai.metrics}/>}
          </div>
          <div>
            <h3>Findings</h3>
            <ul className="ai-findings">{ai.findings.map((f:any)=><li key={f.title} className={f.severity}><b>{f.title}</b><span>{f.detail}</span></li>)}</ul>
            <footer>{ai.engine.toUpperCase()} · {ai.model_version} · CONFIDENCE <b>{fmt(ai.confidence,0)}%</b> · UPDATED {clock(ai.generated_at)}</footer>
          </div>
        </div>:<p>Analysing the latest readings…</p>}
      </section>
    </div>

    <FindingHistory id={id}/>

    <div className="station-grid lower hw-only">
      <section className="device-log">
        <div className="pump-head"><Radio/><span>LIVE TELEMETRY LOG</span><i className="log-pulse"/></div>
        <div className="device-log-rows">
          {[...rows].reverse().slice(0,40).map((r:any)=><div key={r.id}><time>{clock(r.timestamp)}</time><span>LEVEL <b>{fmt(r.water_level_percent,0)}%</b></span>{hasPump?<em className={r.pump_on?"on":""}>{r.pump_on==null?"—":r.pump_on?"PUMP ON":"PUMP OFF"}</em>:<em className={r.flow_rate_l_min>0?"on":""}>{fmt(r.flow_rate_l_min,1)} L/min</em>}<em>{hasPump?(r.pump_run_ms!=null?`motor ${duration(r.pump_run_ms)}`:""):(r.distance_cm!=null?`${fmt(r.distance_cm,1)} cm`:"no echo")}</em>{r.pump_mode&&r.pump_mode!=="A"&&<em className="mode">{COMMAND_LABEL[r.pump_mode]}</em>}</div>)}
          {!rows.length&&<p className="pump-empty">Waiting for the first reading from the device…</p>}
        </div>
      </section>
      <section className="device-card">
        <Radio/><span>CONNECTION</span>
        <strong>{ai?.metrics?.last_seen_seconds!=null&&ai.metrics.last_seen_seconds>30?"OFFLINE":"LIVE HARDWARE"}</strong>
        <p>{!esp32?"Arduino Uno over USB serial, about 2 readings per second":"ESP32-S3 over USB serial, about 1 reading per second"}</p>
        <p>Last reading {clock(reading.timestamp)}</p>
        {hasPump&&<p>Pump ran {ai?.metrics?.duty_cycle_percent_1h!=null?`${fmt(ai.metrics.duty_cycle_percent_1h,0)}%`:"—"} of the last hour</p>}
      </section>
    </div>
    <Disclaimer/>
  </main>;
}
