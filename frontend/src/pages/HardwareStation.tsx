import {Link} from "react-router-dom";
import {useQuery} from "@tanstack/react-query";
import {Area,AreaChart,CartesianGrid,ReferenceLine,ResponsiveContainer,Tooltip,XAxis,YAxis} from "recharts";
import {ArrowLeft,BrainCircuit,Clock,Droplet,Power,Radio,ShieldAlert} from "lucide-react";
import {api} from "../api";
import {Disclaimer,fmt,LiveSocket,Logo} from "../components/Shared";

const START_PERCENT=20, STOP_PERCENT=85;
const STATUS_PILL:Record<string,[string,string]>={normal:["safe","NORMAL"],attention:["warning","ATTENTION"],fault:["critical","FAULT"],offline:["watch","OFFLINE"],no_data:["watch","NO DATA"]};

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

export default function HardwareStation({id,station,reading}:{id:number;station:any;reading:any}){
  const history=useQuery({queryKey:["telemetry",id,"hw"],queryFn:()=>api.telemetry(id,300)});
  const pump=useQuery({queryKey:["pump",id],queryFn:()=>api.pump(id)});
  // Recomputed server-side over the last hour of readings, so poll it rather than refetch on every push.
  const insights=useQuery({queryKey:["insights",id],queryFn:()=>api.insights(id),refetchInterval:2000});

  const rows=(history.data||[]).filter((r:any)=>r.source==="arduino");
  const level=reading.water_level_percent??0;
  const capacity=station.pump_capacity_liters;
  const pumpOn=reading.pump_on??station.pump_status==="on";
  const cycle=pump.data?.current_cycle;
  const cycleMs=cycle?Date.now()-new Date(cycle.triggered_at).getTime():0;
  const ai=insights.data;
  const [pillClass,pillLabel]=STATUS_PILL[ai?.status]||["watch","ANALYSING"];
  const chart=rows.map((r:any)=>({time:clock(r.timestamp),level:r.water_level_percent,pump:r.pump_on?100:0}));
  const levelSeries=rows.map((r:any)=>r.water_level_percent).filter((v:any)=>v!=null).slice(-60);

  return <main className="station-page">
    <nav className="station-nav"><Link to="/dashboard/stations"><ArrowLeft/> Back to network</Link><Logo dark/><LiveSocket/></nav>

    <header className="station-hero">
      <div>
        <span>{station.station_code} · <i>LIVE HARDWARE</i></span>
        <h1>{station.name}</h1>
        <p>{station.location_text} / ARDUINO UNO · AUTOMATIC PUMP CONTROLLER</p>
      </div>
      <div className={`station-risk ${pillClass}`}>
        <span className={`status status-${pillClass}`}><i/>{pillLabel}</span>
        <strong>{fmt(level,0)}<small>%</small></strong>
        <span>TANK LEVEL</span>
        <p><Clock/> UPDATED {clock(reading.timestamp)}</p>
      </div>
    </header>

    <section className="telemetry-blocks hw-sensors">
      <div className="telemetry-block"><span>WATER LEVEL</span><div><b>{fmt(level,0)}</b><small>%</small></div><svg viewBox="0 0 160 30"><path d={sparkPath(levelSeries)}/></svg><p><i/> RAW ADC {reading.level_raw??"—"}</p></div>
      <div className="telemetry-block"><span>WATER IN TANK</span><div><b>{Math.round(level/100*capacity).toLocaleString()}</b><small>L</small></div><p className="hw-sub">of {capacity.toLocaleString()} L capacity</p></div>
      <div className={`telemetry-block hw-pump ${pumpOn?"on":""}`}><span>PUMP MOTOR</span><div><b>{pumpOn?"ON":"OFF"}</b></div><p className="hw-sub">{pumpOn?`running ${duration(cycleMs)}`:`starts at ≤${START_PERCENT}%`}</p></div>
      <div className={`telemetry-block ${reading.water_contact?"hw-alert":""}`}><span>WATER CONTACT</span><div><b>{reading.water_contact==null?"—":reading.water_contact?"WET":"DRY"}</b></div><p className="hw-sub">base leak sensor</p></div>
      <div className="telemetry-block"><span>MOTION</span><div><b>{reading.motion==null?"—":reading.motion?"YES":"NONE"}</b></div><p className="hw-sub">{reading.motion==null?"PIR warming up":"PIR sensor"}</p></div>
    </section>

    <section className="pump-panel lead">
      <div className="pump-head"><Droplet/><span>AUTOMATIC PUMP CONTROL</span></div>
      <div className="pump-top">
        <div className={`pump-indicator ${pumpOn?"on":"off"}`}><Power/>{pumpOn?"PUMPING NOW":"IDLE"}</div>
        <p>The controller starts the motor at ≤{START_PERCENT}% and stops it at ≥{STOP_PERCENT}%. Volume is metered from the motor's real run time at the rated {pump.data?.flow_rate_lpm??20} L/min.</p>
      </div>
      <div className="pump-prediction">
        <div><span>THIS CYCLE</span><b>{cycle?`${fmt(cycle.volume_liters,1)} L`:"—"}</b></div>
        <div><span>TOTAL PUMPED</span><b>{fmt(pump.data?.total_volume_liters,1)} L</b></div>
        <div><span>COMPLETED CYCLES</span><b>{pump.data?.total_cycles??0}</b></div>
        <div><span>NEXT LIKELY RUN</span><b>{pump.data?.prediction?`${pump.data.prediction.predicted_weekday.slice(0,3)} ~${String(pump.data.prediction.predicted_hour).padStart(2,"0")}:00`:"—"}</b></div>
      </div>
      {!pump.data?.prediction&&<p className="pump-empty">The schedule prediction appears after the first full cycle (empty to {STOP_PERCENT}%) moves water.</p>}
      {pump.data?.recent_events?.length>0&&<div className="pump-history"><span>RECENT CYCLES</span>{pump.data.recent_events.slice(0,6).map((e:any)=><div key={e.id}><time>{new Date(e.triggered_at).toLocaleString([],{month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"})}</time><b>{fmt(e.volume_liters,1)} L</b><time>{fmt(e.trigger_level,0)}% → {fmt(e.stop_level,0)}%</time></div>)}</div>}
    </section>

    <div className="station-grid">
      <section className="panel history-panel">
        <div className="panel-head"><div><span>LIVE · LAST {rows.length} READINGS</span><h2>Tank level and pump activity</h2></div></div>
        <ResponsiveContainer width="100%" height={320}>
          <AreaChart data={chart}>
            <defs><linearGradient id="lvl" x1="0" y1="0" x2="0" y2="1"><stop stopColor="#23d5e7" stopOpacity=".35"/><stop offset="1" stopColor="#23d5e7" stopOpacity="0"/></linearGradient></defs>
            <CartesianGrid stroke="#17313a" vertical={false}/>
            <XAxis dataKey="time" stroke="#68838c" minTickGap={50}/>
            <YAxis domain={[0,100]} stroke="#68838c" unit="%"/>
            <Tooltip contentStyle={{background:"#071b23",border:"1px solid #25414a"}} formatter={(v:any,n:any)=>n==="Pump"?[v?"ON":"OFF",n]:[`${v}%`,n]}/>
            <Area type="stepAfter" dataKey="pump" stroke="none" fill="#55e68a" fillOpacity={.12} name="Pump" isAnimationActive={false}/>
            <Area type="monotone" dataKey="level" stroke="#23d5e7" fill="url(#lvl)" name="Level" isAnimationActive={false}/>
            <ReferenceLine y={STOP_PERCENT} stroke="#55e68a" strokeDasharray="4 4" label={{value:`STOP ${STOP_PERCENT}%`,fill:"#55e68a",fontSize:9,position:"insideTopRight"}}/>
            <ReferenceLine y={START_PERCENT} stroke="#ffb547" strokeDasharray="4 4" label={{value:`START ${START_PERCENT}%`,fill:"#ffb547",fontSize:9,position:"insideBottomRight"}}/>
          </AreaChart>
        </ResponsiveContainer>
        <div className="chart-key"><span><i className="cyan"/>Tank level</span><span><i className="green"/>Pump running</span><span>Dashed lines: controller start / stop points</span></div>
      </section>

      <section className={`ai-panel ${pillClass}`}>
        <div className="ai-title"><BrainCircuit/><span>WATERSENSE AI · TANK &amp; PUMP</span></div>
        <span className={`status status-${pillClass}`}><i/>{pillLabel}</span>
        {ai?<>
          <h2 className="ai-headline">{ai.headline}</h2>
          <p>{ai.summary}</p>
          <h3>Findings</h3>
          <ul className="ai-findings">{ai.findings.map((f:any)=><li key={f.title} className={f.severity}><b>{f.title}</b><span>{f.detail}</span></li>)}</ul>
          <aside><ShieldAlert/><div><h3>Recommended action</h3><p>{ai.recommended_action}</p></div></aside>
          <footer>{ai.engine.toUpperCase()} · {ai.model_version} · CONFIDENCE <b>{fmt(ai.confidence,0)}%</b></footer>
        </>:<p>Analysing the latest readings…</p>}
      </section>
    </div>

    <div className="station-grid lower hw-only">
      <section className="device-log">
        <div className="pump-head"><Radio/><span>LIVE TELEMETRY LOG</span><i className="log-pulse"/></div>
        <div className="device-log-rows">
          {[...rows].reverse().slice(0,40).map((r:any)=><div key={r.id}><time>{clock(r.timestamp)}</time><span>LEVEL <b>{fmt(r.water_level_percent,0)}%</b></span><em className={r.pump_on?"on":""}>{r.pump_on==null?"—":r.pump_on?"PUMP ON":"PUMP OFF"}</em><em>{r.pump_run_ms!=null?`motor ${duration(r.pump_run_ms)}`:""}</em></div>)}
          {!rows.length&&<p className="pump-empty">Waiting for the first reading from the device…</p>}
        </div>
      </section>
      <section className="device-card">
        <Radio/><span>CONNECTION</span>
        <strong>{ai?.metrics?.last_seen_seconds!=null&&ai.metrics.last_seen_seconds>30?"OFFLINE":"LIVE HARDWARE"}</strong>
        <p>Arduino Uno over USB serial, about 2 readings per second</p>
        <p>Last reading {clock(reading.timestamp)}</p>
        <p>Pump ran {ai?.metrics?.duty_cycle_percent_1h!=null?`${fmt(ai.metrics.duty_cycle_percent_1h,0)}%`:"—"} of the last hour</p>
      </section>
    </div>
    <Disclaimer/>
  </main>;
}
