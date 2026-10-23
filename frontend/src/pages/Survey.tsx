import {useMemo,useRef,useState} from "react";import {Link} from "react-router-dom";import {ArrowLeft,ArrowRight,Check} from "lucide-react";import {api} from "../api";import {Logo} from "../components/Shared";

type Q={id:string;text:string;type:"single"|"multi"|"text";options?:string[];max?:number;note?:string;show?:(a:Answers)=>boolean;optional?:boolean};
type Answers=Record<string,string|string[]|undefined>;

const QUESTIONS:Q[]=[
{id:"location",text:"Where do you live?",type:"single",options:["Nairobi","Another part of Kenya","Outside Kenya"]},
{id:"residence_type",text:"What best describes your residence?",type:"single",options:["Standalone house","Apartment or flat","Bedsitter or single room","Shared residence","Other"]},
{id:"water_source",text:"What is your main source of water?",type:"single",options:["Piped water","Water vendor","Borehole","Well or spring","Rainwater","A combination of sources","Other"]},
{id:"has_tank",text:"Does your home or property have a water storage tank?",type:"single",options:["Yes","No","Not sure"]},
{id:"has_pump",text:"Does your home or property use an electric water pump to fill a tank?",type:"single",options:["Yes","No","Not sure"]},
{id:"pump_control",text:"How is the pump usually controlled?",type:"single",options:["Manually switched on and off","Automatically controlled by a float switch or similar device","Controlled through a smart or remote system","Another method","Not sure"],show:a=>a.has_pump==="Yes"},
{id:"problems",text:"Have you experienced any of these water-pumping problems?",type:"multi",options:["Tank overflowing","Tank running empty unexpectedly","Pump running when it should not","Pump failure or breakdown","High electricity consumption from pumping","Difficulty knowing the tank's water level","Water supply interruptions","None of these","Other"],note:"Select all that apply."},
{id:"problem_frequency",text:"How often do you experience problems with water availability or pumping?",type:"single",options:["Daily","Several times a week","About once a week","A few times a month","Rarely","Never"]},
{id:"auto_control_usefulness",text:"How useful would automatic pump control that stops filling when the tank reaches a set level be to you?",type:"single",options:["Very useful","Somewhat useful","Neither useful nor useless","Slightly useful","Not useful","Not sure"]},
{id:"desired_features",text:"Which features would be most useful to you?",type:"multi",max:3,options:["Automatic pump switching","Tank-level monitoring on a phone","Alerts when water is running low","Alerts when the pump may have a problem","Predictions of when the tank may need refilling","Monitoring multiple tanks","Monitoring electricity or water usage","None of these","Other"],note:"Pick up to 3."},
{id:"purchase_intent",text:"Would you consider buying a smart automatic water pump if it met your needs and fit your budget?",type:"single",options:["Definitely","Probably","Not sure","Probably not","Definitely not"]},
{id:"price_range",text:"What price range would you consider reasonable for a complete smart automatic pump system?",type:"single",note:"Assume the price includes the pump, automatic controller and tank-level sensor. Installation may cost extra. These are survey price ranges, not WaterSense AI's official prices.",options:["Less than KSh 10,000","KSh 10,000-19,999","KSh 20,000-29,999","KSh 30,000-39,999","KSh 40,000 or more","I would not buy one","Not sure"]},
{id:"main_concern",text:"What would concern you most about buying such a system?",type:"single",options:["Price","Reliability","Electricity consumption","Installation complexity","Repair and maintenance costs","Internet connectivity requirements","Privacy or data security","I do not need one","Other"]},
{id:"other_comments",text:"Is there anything else you would like an automatic water pump to do?",type:"text",optional:true,note:"Optional. Up to 500 characters. Please do not include your name, phone number or other personal information."},
];

function newIdempotencyKey(){try{return crypto.randomUUID()}catch{return `k-${Date.now()}-${Math.random().toString(36).slice(2)}`}}

export default function Survey(){
  const [answers,setAnswers]=useState<Answers>({});
  const [step,setStep]=useState(0);
  const [status,setStatus]=useState<"form"|"submitting"|"done"|"error">("form");
  const [error,setError]=useState("");
  const idempotencyKey=useRef(newIdempotencyKey());
  const active=useMemo(()=>QUESTIONS.filter(q=>!q.show||q.show(answers)),[answers]);
  const q=active[step];
  const total=active.length;
  const value=answers[q.id];

  function set(id:string,v:string|string[]){setAnswers(a=>({...a,[id]:v}))}

  function goNext(){
    if(step<total-1)setStep(step+1);
    else submit();
  }
  function goBack(){if(step>0)setStep(step-1)}

  function selectSingle(opt:string){
    set(q.id,opt);
    window.setTimeout(()=>{if(step<total-1)setStep(s=>s+1);else submit({...answers,[q.id]:opt})},220);
  }
  function toggleMulti(opt:string){
    const current=(value as string[]|undefined)||[];
    if(current.includes(opt)){set(q.id,current.filter(x=>x!==opt));return}
    if(q.max&&current.length>=q.max)return;
    set(q.id,[...current,opt]);
  }

  async function submit(finalAnswers:Answers=answers){
    setStatus("submitting");setError("");
    const payload:any={idempotency_key:idempotencyKey.current,...finalAnswers};
    if(!payload.pump_control)delete payload.pump_control;
    if(!payload.problems)payload.problems=[];
    if(!payload.desired_features)payload.desired_features=[];
    if(!payload.other_comments)delete payload.other_comments;
    try{
      await api.submitSurvey(payload);
      setStatus("done");
    }catch(e:any){
      setStatus("error");
      setError(e?.message||"Something went wrong. Please try again.");
    }
  }

  const canAdvance=q.type==="text"?true:q.type==="single"?!!value:Array.isArray(value)&&value.length>0;

  if(status==="done")return <main className="survey-page"><div className="survey-thanks"><Check size={34}/><h1>Thank you</h1><p>Your response has been recorded. This takes a couple of minutes for one person and genuinely helps us build something people actually need.</p><Link to="/" className="land-text-link">Back to WaterSense AI</Link></div></main>;

  return <main className="survey-page">
    <nav className="survey-nav"><Logo dark/><span className="survey-progress-label">Question {step+1} of {total}</span></nav>
    <div className="survey-progress"><i style={{width:`${((step)/total)*100}%`}}/></div>
    <div className="survey-intro"><h2>Water Use and Smart Pumping Survey</h2><p>We are conducting a short research survey to understand how households and property managers access, store and manage water. Your responses will help us research practical ways to improve automatic water pumping and water storage management. The survey takes approximately 2-3 minutes. Participation is voluntary, and responses will be used for academic research and product development. Please do not include your name, phone number or other identifying information.</p></div>
    <div className="survey-card" key={q.id}>
      <h3>{q.text}</h3>
      {q.note&&<p className="survey-note">{q.note}</p>}
      {q.type==="single"&&<div className="survey-options">{q.options!.map(opt=><button key={opt} className={`survey-option ${value===opt?"selected":""}`} onClick={()=>selectSingle(opt)}>{opt}</button>)}</div>}
      {q.type==="multi"&&<div className="survey-options">{q.options!.map(opt=>{const sel=((value as string[]|undefined)||[]).includes(opt);return <button key={opt} className={`survey-option multi ${sel?"selected":""}`} onClick={()=>toggleMulti(opt)}><span className="survey-check">{sel&&<Check size={13}/>}</span>{opt}</button>})}</div>}
      {q.type==="text"&&<div className="survey-text"><textarea maxLength={500} value={(value as string)||""} onChange={e=>set(q.id,e.target.value)} placeholder="Optional"/><small>{((value as string)||"").length}/500</small></div>}
      {status==="error"&&<p className="survey-error">{error}</p>}
      <div className="survey-actions">
        <button className="survey-back" onClick={goBack} disabled={step===0}><ArrowLeft size={15}/> Back</button>
        {(q.type!=="single")&&<button className="survey-next" onClick={goNext} disabled={!canAdvance&&!q.optional||status==="submitting"}>{status==="submitting"?"Submitting...":step<total-1?<>Next <ArrowRight size={15}/></>:<>Submit <ArrowRight size={15}/></>}</button>}
      </div>
    </div>
  </main>;
}
