"""hadith.py - Per-day hadith with local cache — RAM-only dict + disk fallback."""
import json, time, hashlib, random
from pathlib import Path
import httpx

CACHE_DIR = Path(__file__).resolve().parent / "data"
CACHE = CACHE_DIR / "hadith.json"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

UMMAH_BASE = "https://api.ummahapi.com/v1/hadith/bukhari/random"

BOOKS = {
    "bukhari": "https://api.ummahapi.com/v1/hadith/bukhari/random",
    "muslim":  "https://api.ummahapi.com/v1/hadith/muslim/random",
}

def _seed_today() -> str:
    today = time.strftime("%Y-%m-%d")
    return hashlib.sha256(today.encode()).hexdigest()[:8]

def get(collection: str = "bukhari") -> dict:
    if not CACHE.exists():
        CACHE.write_text("[]", encoding="utf-8")
    try:
        rows = json.loads(CACHE.read_text(encoding="utf-8"))
    except:
        rows = []
    seed = _seed_today()
    for r in rows:
        if r.get("seed") == seed and r.get("collection") == collection:
            return r["payload"]
    # fetch + append
    try:
        with httpx.Client(timeout=20) as c:
            r = c.get(BOOKS.get(collection, BOOKS["bukhari"]))
            r.raise_for_status()
            payload = r.json()
    except Exception as e:
        # Fallback sample
        payload = {"hadith": "Sample hadith - UmmahAPI unreachable", "collection": collection, "error": str(e)}
    
    rows.append({"seed": seed, "collection": collection, "payload": payload, "date": time.strftime("%Y-%m-%d")})
    # Keep last 30 days
    rows = rows[-30:]
    CACHE.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
