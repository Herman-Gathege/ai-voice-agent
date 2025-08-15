# real_estate_functions.py
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

# In-memory stores (replace with DB/Calendar later)
APPTS_DB = {"appointments": {}, "next_id": 1}
LEADS_DB = []

# Company availability (customize)
BUSINESS_TIMEZONE = "America/Chicago"   # Vertex team TZ for storage
BUSINESS_DAYS_AHEAD = 14                # offer within next 2 weeks
BUSINESS_HOURS = (time(9, 0), time(17, 0))  # 9am–5pm local

def _is_same_day(dt_a, dt_b):
    return dt_a.date() == dt_b.date()

def _as_tz(dt, tz):
    return dt.astimezone(ZoneInfo(tz))

def _next_business_day(now_company_tz):
    # Never book same-day; start from tomorrow
    return (now_company_tz + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

def _generate_slots_for_day(day_company_tz, preference="morning"):
    start, end = BUSINESS_HOURS
    base = day_company_tz.replace(hour=0, minute=0, second=0, microsecond=0)
    # Simple buckets
    if preference == "afternoon":
        windows = [(time(13, 0), time(17, 0))]
    else:
        windows = [(time(9, 0), time(12, 0))]

    # 30-minute slots
    slots = []
    for win_start, win_end in windows:
        cur = base.replace(hour=win_start.hour, minute=win_start.minute)
        end_dt = base.replace(hour=win_end.hour, minute=win_end.minute)
        while cur < end_dt:
            slots.append(cur)
            cur += timedelta(minutes=30)
    return slots

def get_available_slots(caller_timezone: str, day_hint: str = "tomorrow", preference: str = "morning"):
    """
    Returns two suggested ISO datetimes in the caller's timezone and the stored company timezone UTC equivalence.
    - caller_timezone: e.g., "America/New_York". Must be an IANA zone.
    - day_hint: "tomorrow", "day_after", or an ISO date "YYYY-MM-DD"
    - preference: "morning" or "afternoon"
    """
    now_company = datetime.now(ZoneInfo(BUSINESS_TIMEZONE))
    start_day = _next_business_day(now_company)

    if day_hint not in ("tomorrow", "day_after"):
        # try explicit date
        try:
            y, m, d = map(int, day_hint.split("-"))
            start_day = start_day.replace(year=y, month=m, day=d)
        except Exception:
            pass
    else:
        if day_hint == "day_after":
            start_day += timedelta(days=1)

    # Clamp within scheduling window
    latest_day = now_company + timedelta(days=BUSINESS_DAYS_AHEAD)
    if start_day > latest_day:
        start_day = latest_day

    # Build candidate slots in company tz
    candidates = _generate_slots_for_day(start_day, preference)

    # Pick two that are not already taken
    taken = {a["start_iso_company"] for a in APPTS_DB["appointments"].values()}
    free = [dt for dt in candidates if dt.isoformat() not in taken][:2]

    if not free:
        return {"error": "No slots available. Try another day or preference."}

    # Convert to caller TZ for display
    caller_tz = ZoneInfo(caller_timezone)
    suggestions = []
    for dt in free:
        suggestions.append({
            "display_caller_tz": _as_tz(dt, caller_timezone).isoformat(),
            "start_iso_company": dt.isoformat(),  # store as company tz
        })
    return {"slots": suggestions, "company_timezone": BUSINESS_TIMEZONE}

def book_appointment(full_name: str, email: str, caller_timezone: str, start_iso_company: str, notes: str = ""):
    """
    Books an appointment at a specific company-timezone ISO start.
    Validates basic email format and uniqueness of slot.
    """
    if "@" not in email or "." not in email.split("@")[-1]:
        return {"error": "Invalid email format."}

    # Prevent double-booking
    for appt in APPTS_DB["appointments"].values():
        if appt["start_iso_company"] == start_iso_company:
            return {"error": "That time was just taken. Please pick another slot."}

    appt_id = APPTS_DB["next_id"]
    APPTS_DB["next_id"] += 1

    APPTS_DB["appointments"][appt_id] = {
        "id": appt_id,
        "name": full_name,
        "email": email,
        "caller_timezone": caller_timezone,
        "start_iso_company": start_iso_company,
        "notes": notes,
        "status": "scheduled"
    }
    return {
        "appointment_id": appt_id,
        "message": f"Booked for {full_name}.",
        "start_iso_company": start_iso_company
    }

def save_lead(full_name: str, email: str, goal: str = "", pains: list[str] = None):
    """Optional: persist lead context captured during the call."""
    LEADS_DB.append({
        "name": full_name,
        "email": email,
        "goal": goal,
        "pains": pains or []
    })
    return {"status": "saved", "count": len(LEADS_DB)}

# Function map exposed to the agent
FUNCTION_MAP = {
    "get_available_slots": get_available_slots,
    "book_appointment": book_appointment,
    "save_lead": save_lead
}
