"""History of WaterSense AI findings.

Each finding the tank analysis raises becomes an episode: opened the first time
it appears, extended every time a later analysis confirms it, and closed once it
has been absent for RESOLVE_AFTER_S. The grace period stops a finding that
flickers on a threshold (short-cycling at exactly 4 starts, a level hovering at
10%) from turning into dozens of one-second episodes.
"""
from datetime import timedelta
from sqlalchemy import select, desc
from ..models import AiFinding

RESOLVE_AFTER_S=60
SEVERITY_RANK={"critical":0,"warning":1,"info":2}
# "Operating normally" is the absence of findings, not something to log.
IGNORED_TITLES={"Operating normally"}
CONTEXT_KEYS=("level_percent","liters_in_tank","pump_on","level_rate_per_min","current_cycle_minutes","pump_starts_1h","duty_cycle_percent_1h","water_contact")


def record_findings(db,station_id,insights,now):
    """Fold one analysis result into the episode table. Caller commits."""
    current={f["title"]:f for f in insights.get("findings",[]) if f["title"] not in IGNORED_TITLES}
    open_rows={r.title:r for r in db.scalars(select(AiFinding).where(AiFinding.station_id==station_id,AiFinding.resolved_at.is_(None))).all()}
    metrics=insights.get("metrics") or {}
    context={k:metrics[k] for k in CONTEXT_KEYS if k in metrics}
    context["headline"]=insights.get("headline")

    for title,f in current.items():
        row=open_rows.get(title)
        if row is None:
            db.add(AiFinding(station_id=station_id,title=title,severity=f["severity"],first_detail=f["detail"],last_detail=f["detail"],
                             first_seen=now,last_seen=now,checks=1,context=context,action=insights.get("recommended_action")))
            continue
        row.last_seen=now;row.last_detail=f["detail"];row.checks+=1
        if SEVERITY_RANK.get(f["severity"],9)<SEVERITY_RANK.get(row.severity,9):row.severity=f["severity"]

    cutoff=now-timedelta(seconds=RESOLVE_AFTER_S)
    for title,row in open_rows.items():
        if title not in current and row.last_seen<=cutoff:
            row.resolved_at=row.last_seen  # it was last confirmed then, not when we noticed


def finding_dict(r,now):
    end=r.resolved_at or now
    return {"id":r.id,"title":r.title,"severity":r.severity,"active":r.resolved_at is None,
            "first_seen":r.first_seen.isoformat()+"Z","last_seen":r.last_seen.isoformat()+"Z",
            "resolved_at":r.resolved_at.isoformat()+"Z" if r.resolved_at else None,
            "duration_seconds":max(0,int((end-r.first_seen).total_seconds())),"checks":r.checks,
            "first_detail":r.first_detail,"last_detail":r.last_detail,"context":r.context or {},"action":r.action}


def finding_history(db,station_id,now,hours=24,limit=100):
    since=now-timedelta(hours=hours)
    rows=db.scalars(select(AiFinding).where(AiFinding.station_id==station_id,AiFinding.last_seen>=since)
                    .order_by(desc(AiFinding.first_seen)).limit(limit)).all()
    items=[finding_dict(r,now) for r in rows]
    by_title={}
    for i in items:
        t=by_title.setdefault(i["title"],{"title":i["title"],"severity":i["severity"],"episodes":0,"total_seconds":0,"last_seen":i["last_seen"]})
        t["episodes"]+=1;t["total_seconds"]+=i["duration_seconds"]
        if SEVERITY_RANK.get(i["severity"],9)<SEVERITY_RANK.get(t["severity"],9):t["severity"]=i["severity"]
        if i["last_seen"]>t["last_seen"]:t["last_seen"]=i["last_seen"]
    summary=sorted(by_title.values(),key=lambda t:(SEVERITY_RANK.get(t["severity"],9),-t["episodes"]))
    return {"hours":hours,"active":sum(1 for i in items if i["active"]),"total":len(items),"by_title":summary,"items":items}
