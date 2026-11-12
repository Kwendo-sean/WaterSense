"""Operator control of a hardware pump: manual override plus timed schedules.

Resolved into a one-character command the serial bridge forwards to the
controller on every reading:
  A  automatic (the controller's own 20% / 85% float-switch logic)
  1  manual on       0  manual off       S  on because a schedule is running
A forced run always stops at a full tank; the controller enforces that itself.
"""
from datetime import datetime, time, timedelta
from .pump import _local

FULL_PERCENT=100.0
MODES=("auto","on","off")

def local_now(now_utc):
    return _local(now_utc)

def _start(date, hhmm, tz):
    h,m=map(int,hhmm.split(":"))
    return datetime.combine(date,time(h,m),tzinfo=tz)

def first_run_date(hhmm, duration_minutes, now_local):
    """A one-off schedule fires at the next occurrence of its time; if that
    window is already under way today it starts immediately."""
    start=_start(now_local.date(),hhmm,now_local.tzinfo)
    if start+timedelta(minutes=duration_minutes)<=now_local: start+=timedelta(days=1)
    return start.date().isoformat()

SCHEDULE_MAX_DAYS=31

def check_run_date(run_date, hhmm, duration_minutes, now_local):
    """Validate an operator-chosen one-off date. Returns an error message or None."""
    try: day=datetime.fromisoformat(run_date).date()
    except ValueError: return "Not a valid date."
    if day>now_local.date()+timedelta(days=SCHEDULE_MAX_DAYS):
        return f"Schedules can be set up to {SCHEDULE_MAX_DAYS} days ahead."
    if _start(day,hhmm,now_local.tzinfo)+timedelta(minutes=duration_minutes)<=now_local:
        return "That time has already passed."
    return None

def window(schedule, now_local):
    """(start, end) of the schedule window containing now_local, else None."""
    span=timedelta(minutes=schedule.duration_minutes)
    if schedule.repeat=="once":
        if not schedule.run_date: return None
        candidates=[datetime.fromisoformat(schedule.run_date).date()]
    else:  # daily; yesterday's window may run past midnight
        candidates=[now_local.date(),now_local.date()-timedelta(days=1)]
    for d in candidates:
        start=_start(d,schedule.start_time,now_local.tzinfo)
        if start<=now_local<start+span: return start,start+span
    return None

def next_run(schedule, now_local):
    if not schedule.enabled: return None
    if schedule.repeat=="once":
        start=_start(datetime.fromisoformat(schedule.run_date).date(),schedule.start_time,now_local.tzinfo)
        return start if start+timedelta(minutes=schedule.duration_minutes)>now_local else None
    start=_start(now_local.date(),schedule.start_time,now_local.tzinfo)
    current=window(schedule,now_local)
    if current and schedule.done_on!=current[0].date().isoformat(): return current[0]
    return start if start>now_local else start+timedelta(days=1)

def resolve(control, schedules, level, now_local):
    """Pick the command for this reading. Mutates control/schedules when a run
    ends (window over, or tank full) and returns (command, active, changed)."""
    changed=False
    full=level is not None and level>=FULL_PERCENT
    if control is not None and control.mode=="on" and full:
        control.mode="auto";changed=True  # manual fill done: hand back to automatic
    active=None
    for s in schedules:
        if not s.enabled: continue
        w=window(s,now_local)
        if s.repeat=="once" and w is None and next_run(s,now_local) is None:
            s.enabled=False;changed=True;continue
        if not w or s.done_on==w[0].date().isoformat(): continue
        if full:
            s.done_on=w[0].date().isoformat();changed=True
            if s.repeat=="once": s.enabled=False
            continue
        if active is None: active=(s,w)
    mode=control.mode if control is not None else "auto"
    command={"on":"1","off":"0"}.get(mode) or ("S" if active else "A")
    return command,active,changed
