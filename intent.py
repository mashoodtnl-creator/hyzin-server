"""Small, deterministic command parser; model fallback never supplies verse content."""
import json
import re
import unicodedata
from dataclasses import dataclass

import quran


@dataclass(frozen=True)
class Intent:
    action: str
    surah: int | None = None
    ayah: int | None = None


ACTIONS = {
    "repeat": ("repeat", "again", "വീണ്ടും", "മറുവട്ടം", "மீண்டும்"),
    "next": ("next", "അടുത്ത", "அடுத்த"),
    "previous": ("previous", "മുൻപത്തെ", "മുമ്പത്തെ", "previous", "முந்தைய"),
    "slow": ("slow", "slowly", "പതുക്കെ", "മെല്ലെ", "மெதுவாக"),
    "check": ("check", "correct me", "തിരുത്ത", "ഓതി നോക്ക", "പരിശോധി", "சரிபார்"),
}
CUES = ("surah", "sura", "soorah", "sourah", "ayah", "ayat", "verse",
        "സൂറ", "സുറ", "ആയത്ത്", "ആയത്", "ഓത", "ചൊല്ല", "سورة", "آية", "سوره",
        "ஸூர", "ஆயத்", "ஓது", "quran", "ഖുർആൻ", "குர்ஆன்")


def _canonical(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = re.sub(r"[\u064b-\u065f\u0670\u06d6-\u06ed]", "", text)
    return re.sub(r"[\s\-_'’]+", "", text)


def surah_number(text: str) -> int | None:
    compact = _canonical(text)
    _, _, surahs = quran.corpus()
    candidates = []
    for row, malayalam in zip(surahs, quran.MALAYALAM_NAMES):
        for name in (row["english"], row["name"].replace("سُورَةُ", ""), malayalam):
            candidate = _canonical(name)
            if len(candidate) >= (2 if any("\u0600" <= c <= "\u06ff" for c in candidate) else 3):
                candidates.append((candidate, row["number"]))
    for candidate, number in sorted(candidates, key=lambda item: len(item[0]), reverse=True):
        if candidate in compact:
            return number
    aliases = {"صٓ": 38, "قٓ": 50, "surah sad": 38, "surah qaf": 50,"ഫാതിഹ": 1, "ഫാതിഹാ": 1, "fatiha": 1, "al fatiha": 1,
               "baqarah": 2, "ബഖറ": 2, "yaseen": 36, "യാസീൻ": 36,
               "ikhlas": 112, "ഇഖ്ലാസ്": 112, "nas": 114, "നാസ്": 114, "அல்ஃபாத்திஹா": 1, "அல்பாத்திஹா": 1,
               "இக்லாஸ்": 112, "பகரா": 2}
    for alias, number in aliases.items():
        if _canonical(alias) in compact:
            return number
    match = re.search(r"(?:surah|sura|സൂറത്ത്|സൂറ|ஸூரா|سورة)\s*(\d{1,3})", text.casefold())
    if match:
        return int(match.group(1))
    return None


def parse(text: str) -> Intent | None:
    lowered = text.casefold()
    if any(key in lowered for key in ("daily ayah", "today's ayah", "ഇന്നത്തെ ആയത്ത്", "தினசரி ஆயத்")):
        return Intent("daily_ayah")
    if any(key in lowered for key in ("daily dua", "today's dua", "ഇന്നത്തെ ദുആ", "தினசரி துஆ")):
        return Intent("daily_dua")
    surah = surah_number(text)
    ayah_match = re.search(r"(?:ayah|ayat|verse|ആയത്ത്|ആയത്|آية|ஆயத்)\s*(\d{1,3})", lowered)
    ayah = int(ayah_match.group(1)) if ayah_match else None
    for action, keywords in ACTIONS.items():
        if any(word in lowered for word in keywords):
            return Intent(action, surah, ayah)
    if surah is not None or ayah is not None:
        return Intent("play", surah, ayah)
    return None


def looks_quran_related(text: str) -> bool:
    lowered = text.casefold()
    return any(key in lowered for key in CUES)


def fallback(text: str) -> Intent | None:
    """Model only classifies commands; never trust it for scripture or addresses."""
    from providers import _gemini_client
    from google.genai import types

    response = _gemini_client().models.generate_content(
        model="gemini-2.5-flash",
        contents=("Classify ONLY this Quran playback command into JSON with action "
                  "(play/repeat/next/previous/slow/check/none), surah (1..114 or null) "
                  f"and ayah (1..286 or null). Never include Quran text. Command: {text[:256]}"),
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0),
    )
    try:
        result = json.loads(response.text or "{}")
        action = result.get("action")
        surah = result.get("surah")
        ayah = result.get("ayah")
        if action not in {"play", *ACTIONS}:
            return None
        if surah is not None and (type(surah) is not int or not 1 <= surah <= 114):
            return None
        if ayah is not None and (type(ayah) is not int or not 1 <= ayah <= 286):
            return None
        return Intent(action, surah, ayah)
    except (ValueError, TypeError, AttributeError):
        return None
