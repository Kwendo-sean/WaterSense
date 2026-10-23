import {useState} from "react";import {useQuery} from "@tanstack/react-query";import {Link} from "react-router-dom";import {ArrowLeft,Download} from "lucide-react";import {api,API,getAdminKey,setAdminKey,clearAdminKey} from "../api";import {Logo,Loading,ErrorState} from "../components/Shared";

function Bar({label,count,pct}:{label:string;count:number;pct:number}){return <div className="survey-bar-row"><div className="survey-bar-label"><span>{label}</span><b>{count} · {pct}%</b></div><div className="survey-bar-track"><i style={{width:`${Math.min(100,pct)}%`}}/></div></div>}

function Block({title,denomNote,rows}:{title:string;denomNote?:string;rows:{option:string;count:number;pct:number}[]}){
  if(!rows||!rows.length)return null;
  return <section className="panel survey-block"><div className="panel-head"><div><span>{denomNote||"ALL RESPONDENTS"}</span><h2>{title}</h2></div></div><div className="survey-bars">{rows.map(r=><Bar key={r.option} label={r.option} count={r.count} pct={r.pct}/>)}</div></section>;
}

export default function SurveyResults(){
  const [key,setKey]=useState(()=>getAdminKey());
  const [input,setInput]=useState("");
  const results=useQuery({queryKey:["survey-results",key],queryFn:()=>api.surveyResults(key),enabled:!!key,retry:false});

  function trySubmitKey(){setAdminKey(input);setKey(input)}

  async function exportCsv(){
    const r=await fetch(`${API}/api/v1/survey/export`,{headers:{"X-Admin-Key":key}});
    if(!r.ok){alert("Export failed — check your admin key.");return}
    const blob=await r.blob();const url=URL.createObjectURL(blob);
    const a=document.createElement("a");a.href=url;a.download="watersense_survey_export.csv";document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url);
  }

  if(!key||results.error){
    if(results.error)clearAdminKey();
    return <main className="survey-admin-gate"><Logo dark/><h1>Research team access</h1><p>Enter the admin key to view survey results.</p>{results.error&&<p className="survey-error">Access denied — check the key and try again.</p>}<input type="password" value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>e.key==="Enter"&&trySubmitKey()} placeholder="Admin key"/><button onClick={trySubmitKey}>Continue</button></main>;
  }
  if(results.isLoading)return <div className="survey-admin"><Loading/></div>;
  if(!results.data)return <div className="survey-admin"><ErrorState/></div>;
  const d=results.data;

  return <main className="survey-admin">
    <nav className="station-nav"><Link to="/"><ArrowLeft/> Back to site</Link><Logo dark/><button className="survey-export-btn" onClick={exportCsv}><Download size={15}/> Export CSV</button></nav>
    <header className="survey-admin-head">
      <h1>Survey results</h1>
      <p>{d.total_responses} valid response{d.total_responses!==1?"s":""} · {d.collection_start?new Date(d.collection_start).toLocaleDateString():"—"} to {d.collection_end?new Date(d.collection_end).toLocaleDateString():"—"}</p>
      <div className="survey-segments">
        <div><b>{d.segments.all}</b><span>All respondents</span></div>
        <div><b>{d.segments.kenya}</b><span>In Kenya</span></div>
        <div><b>{d.segments.with_tank}</b><span>Have a tank</span></div>
        <div><b>{d.segments.with_pump}</b><span>Have an electric pump</span></div>
      </div>
      <p className="survey-methodology">{d.methodology_note}</p>
    </header>
    <div className="survey-admin-grid">
      <Block title="Location" rows={d.by_location}/>
      <Block title="Residence type" rows={d.by_residence_type}/>
      <Block title="Main water source" rows={d.by_water_source}/>
      <Block title="Has a storage tank" rows={d.has_tank}/>
      <Block title="Uses an electric pump" rows={d.has_pump}/>
      <Block title="Pump control method" denomNote={`AMONG ${d.segments.with_pump} PUMP USERS`} rows={d.pump_control}/>
      <Block title="Problems experienced" denomNote="MULTI-SELECT — CAN EXCEED 100%" rows={d.problems}/>
      <Block title="Problem frequency" rows={d.problem_frequency}/>
      <Block title="Usefulness of automatic control" rows={d.auto_control_usefulness}/>
      <Block title="Most-wanted features" denomNote="MULTI-SELECT, UP TO 3 — CAN EXCEED 100%" rows={d.desired_features}/>
      <Block title="Purchase intent" rows={d.purchase_intent}/>
      <Block title="Acceptable price range" rows={d.price_range}/>
      <Block title="Main concern" rows={d.main_concern}/>
    </div>
    {d.comments?.length>0&&<section className="panel survey-block"><div className="panel-head"><div><span>FREE-TEXT RESPONSES</span><h2>Additional comments ({d.comments.length})</h2></div></div><div className="survey-comments">{d.comments.map((c:string,i:number)=><p key={i}>&ldquo;{c}&rdquo;</p>)}</div></section>}
  </main>;
}
