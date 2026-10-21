
"""dua.py - Morning/evening Azkar + dua — Malayalam forced for kids."""
import json, random
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "data"

def _load_json(name: str):
    p = ROOT / name
    if not p.exists():
        # Fallback sample if file missing
        return [{"title": f"Sample {name}", "arabic": "بسم الله", "ml": "Sample dua", "audio_path": "/audio/dua/sample.wav"}]
    return json.loads(p.read_text(encoding="utf-8"))

def morning() -> dict:
    rows = _load_json("azkar_morning.json")
    return random.choice(rows)

def evening() -> dict:
    rows = _load_json("azkar_evening.json")
    return random.choice(rows)

def all_morning() -> list:
    return _load_json("azkar_morning.json")

def all_evening() -> list:
    return _load_json("azkar_evening.json")

