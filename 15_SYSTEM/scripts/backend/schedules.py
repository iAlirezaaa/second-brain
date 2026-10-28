"""SuperAGI's Schedule logic, minus the APScheduler daemon: pure due-math.

SuperAGI stored schedules with a cron expression and let a Celery beat poll them. This
port keeps the part a stdlib brain needs -- "is this schedule due now, given when it last
ran?" -- as pure functions a loop or a human can call. Two spec forms:

    {"every_minutes": 30}          # at least N minutes since the last run
    {"daily_at": "09:30"}          # the day's HH:MM, rolling to tomorrow when passed

Both are UTC, like every timestamp in this repo.
"""
from datetime import datetime, timedelta, timezone


def parse_utc(text):
    """Parse an ISO timestamp; a trailing Z is accepted (Python 3.9's fromisoformat
    does not). A naive timestamp is read as UTC."""
    s = str(text or "").strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def fmt_utc(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _form(spec):
    if not isinstance(spec, dict):
        raise ValueError("schedule spec must be an object")
    if "every_minutes" in spec:
        minutes = spec["every_minutes"]
        if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes < 1:
            raise ValueError("every_minutes must be a positive int")
        return ("every_minutes", minutes)
    if "daily_at" in spec:
        raw = str(spec["daily_at"] or "").strip()
        parts = raw.split(":")
        if len(parts) != 2:
            raise ValueError("daily_at must be HH:MM, got %r" % raw)
        try:
            hour, minute = int(parts[0]), int(parts[1])
        except ValueError:
            raise ValueError("daily_at must be HH:MM, got %r" % raw)
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("daily_at must be HH:MM, got %r" % raw)
        return ("daily_at", (hour, minute))
    raise ValueError("schedule spec needs every_minutes or daily_at")


def is_due(spec, last_run, now):
    """Due when the schedule's next moment is at or before `now` (UTC datetimes or
    ISO strings; a naive datetime is read as UTC; `last_run` None means never ran,
    so it is due)."""
    kind, value = _form(spec)
    now_dt = now if isinstance(now, datetime) else parse_utc(now)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)
    if last_run is None:
        return True
    last_dt = last_run if isinstance(last_run, datetime) else parse_utc(last_run)
    if last_dt.tzinfo is None:
        last_dt = last_dt.replace(tzinfo=timezone.utc)
    if kind == "every_minutes":
        return now_dt >= last_dt + timedelta(minutes=value)
    hour, minute = value
    cand = last_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if cand <= last_dt:
        cand += timedelta(days=1)
    return cand <= now_dt


def next_run_after(spec, now):
    """The schedule's next moment at or after `now`, as an ISO UTC string."""
    kind, value = _form(spec)
    now_dt = now if isinstance(now, datetime) else parse_utc(now)
    if kind == "every_minutes":
        return fmt_utc(now_dt + timedelta(minutes=value))
    hour, minute = value
    cand = now_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if cand <= now_dt:
        cand += timedelta(days=1)
    return fmt_utc(cand)
