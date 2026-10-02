import math
from datetime import date, datetime, timedelta, timezone

PLACE = {"lat": 41.9, "lon": 12.5, "name": "Italia (predefinita)"}
ZENITH = 90.833


def set_place(lat, lon, name: str = "") -> None:
    if lat is not None and lon is not None:
        PLACE.update(lat=float(lat), lon=float(lon), name=name or f"{float(lat):.3f}, {float(lon):.3f}")


def _event(day: date, rising: bool) -> datetime | None:
    lat, lon = PLACE["lat"], PLACE["lon"]
    n = day.timetuple().tm_yday
    lng_hour = lon / 15
    t = n + ((6 if rising else 18) - lng_hour) / 24
    m = 0.9856 * t - 3.289
    ell = (m + 1.916 * math.sin(math.radians(m)) + 0.020 * math.sin(math.radians(2 * m)) + 282.634) % 360
    ra = math.degrees(math.atan(0.91764 * math.tan(math.radians(ell)))) % 360
    ra = (ra + (math.floor(ell / 90) * 90 - math.floor(ra / 90) * 90)) / 15
    sin_dec = 0.39782 * math.sin(math.radians(ell))
    cos_dec = math.cos(math.asin(sin_dec))
    cos_h = (math.cos(math.radians(ZENITH)) - sin_dec * math.sin(math.radians(lat))) / (cos_dec * math.cos(math.radians(lat)))
    if cos_h > 1 or cos_h < -1:
        return None
    h = (360 - math.degrees(math.acos(cos_h))) if rising else math.degrees(math.acos(cos_h))
    local_t = h / 15 + ra - 0.06571 * t - 6.622
    ut = (local_t - lng_hour) % 24
    base = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    return (base + timedelta(hours=ut)).astimezone()


def times(day: date | None = None) -> dict:
    day = day or date.today()
    return {"sunrise": _event(day, True), "sunset": _event(day, False)}


def next_event(kind: str, offset_min: float = 0, after: datetime | None = None) -> datetime | None:
    after = after or datetime.now().astimezone()
    for i in range(0, 3):
        t = times(after.date() + timedelta(days=i)).get(kind)
        if t and t + timedelta(minutes=offset_min) > after:
            return t + timedelta(minutes=offset_min)
    return None


def up(now: datetime | None = None) -> bool:
    now = now or datetime.now().astimezone()
    t = times(now.date())
    if not t["sunrise"] or not t["sunset"]:
        return 4 <= now.month <= 9
    return t["sunrise"] <= now < t["sunset"]


def entity() -> dict:
    t = times()
    attrs = {"name": "Sole", "alba": t["sunrise"].strftime("%H:%M") if t["sunrise"] else "",
             "tramonto": t["sunset"].strftime("%H:%M") if t["sunset"] else "", "luogo": PLACE["name"]}
    return {"state": "above_horizon" if up() else "below_horizon", "attrs": attrs, "lc": 0}
