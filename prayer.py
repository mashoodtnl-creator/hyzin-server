"""prayer.py - Daily Aladhan timings + Qibla, cached 24h"""
import json, time
from pathlib import Path
from typing import Any
import httpx

CACHE_DIR = Path(__file__).resolve().parent / "data" / "prayer-cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
ALADHAN = "https://api.aladhan.com/v1"

def _key(name: str, **p) -> Path:
    suffix = "_".join(f"{k}={v}" for k, v in sorted(p.items()))
    safe = suffix.replace("/", "_").replace(":", "_")[:100]
    return CACHE_DIR / f"{name}__{safe}.json"

def _cached_or_fetch(name: str, max_age_s: int, url: str, **params) -> dict[str, Any]:
    f = _key(name, **params)
    if f.exists() and (time.time() - f.stat().st_mtime) < max_age_s:
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except:
            pass
    with httpx.Client(timeout=20) as c:
        r = c.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    f.write_text(json.dumps(data), encoding="utf-8")
    return data

def timings(lat: float, lon: float, method: int = 3,
            school: int = 1, tz: str = "Asia/Kolkata") -> dict[str, Any]:
    """Kerala default: MWL method (3), Hanafi school (1)."""
    return _cached_or_fetch(
        "timings", 23 * 3600,
        f"{ALADHAN}/timings",
        latitude=lat, longitude=lon,
        method=method, school=school, timezone=tz,
    )["data"]

def qibla(lat: float, lon: float) -> float:
    """Returns compass bearing (degrees from true north) toward Kaaba."""
    data = _cached_or_fetch(
        "qibla", 30 * 24 * 3600,
        f"{ALADHAN}/qibla/{lat}/{lon}",
    )
    return float(data["data"]["direction"])
