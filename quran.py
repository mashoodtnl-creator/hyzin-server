"""Read-only verse store and conservative Quran recitation word comparison."""
import json
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"


@dataclass(frozen=True)
class Ayah:
    surah: int
    number: int
    arabic: str
    malayalam: str


def read_verses(path: Path) -> dict[tuple[int, int], str]:
    if not path.exists():
        raise FileNotFoundError(f"Quran data missing: {path.name}; run python scripts/fetch_quran.py")
    rows = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line or line.startswith("#"):
            continue
        surah, ayah, text = line.split("|", 2)
        key = (int(surah), int(ayah))
        if key in rows or not text.strip():
            raise ValueError("Invalid or duplicate Quran reference")
        rows[key] = text
    return rows


@lru_cache(maxsize=1)
def corpus():
    arabic = read_verses(DATA / "quran-uthmani.txt")
    malayalam = read_verses(DATA / "ml.abdulhameed.txt")
    names = json.loads((DATA / "surahs.json").read_text(encoding="utf-8"))
    if len(arabic) != 6236 or set(arabic) != set(malayalam) or len(names) != 114:
        raise ValueError("Incomplete Quran dataset")
    if {(s, a) for s, meta in enumerate(names, 1) for a in range(1, meta["ayahs"] + 1)} != set(arabic):
        raise ValueError("Quran chapter metadata does not match the verses")
    return arabic, malayalam, names


def get_ayah(surah: int, ayah: int) -> Ayah:
    arabic, malayalam, _ = corpus()
    if (surah, ayah) not in arabic:
        raise ValueError("Unknown surah/ayah")
    return Ayah(surah, ayah, arabic[surah, ayah], malayalam[surah, ayah])


# Transliteration for search aliases, NOT for sacred text or display; metadata names
# are from alquran.cloud and each chapter also retains its Arabic canonical name.
MALAYALAM_NAMES = """ഫാത്തിഹ ബഖറ ആലു-ഇംറാൻ നിസാഅ് മാഇദ അൻആം അഅ്റാഫ് അൻഫാൽ തൗബ യൂനുസ് ഹൂദ് യൂസുഫ് റഅദ് ഇബ്രാഹീം ഹിജ്റ് നഹ്ൽ ഇസ്റാഅ് കഹ്ഫ് മർയം ത്വാഹാ അൻബിയാഅ് ഹജ്ജ് മുഅ്മിനൂൻ നൂർ ഫുർഖാൻ ശുഅറാഅ് നംല് ഖസസ് അൻകബൂത് റൂം ലുഖ്മാൻ സജ്ദ അഹ്സാബ് സബഅ് ഫാത്വിർ യാസീൻ സ്വാഫ്ഫാത്ത് സ്വാദ് സുമർ ഗാഫിർ ഫുസ്സിലത്ത് ശൂറ സുഖ്റുഫ് ദുഖാൻ ജാഥിയ അഹ്ഖാഫ് മുഹമ്മദ് ഫത്ഹ് ഹുജുറാത്ത് ഖാഫ് ദാരിയാത്ത് ത്വൂർ നജ്മ് ഖമർ റഹ്മാൻ വാഖിഅ ഹദീദ് മുജാദില ഹശ്റ് മുംതഹിന സ്വഫ്ഫ് ജുമുഅ മുനാഫിഖൂൻ തഗാബുൻ ത്വലാഖ് തഹ്റീം മുൽക് ഖലം ഹാഖ്ഖ മആരിജ് നൂഹ് ജിന്ന് മുസ്സമ്മിൽ മുദ്ദസ്സിർ ഖിയാമ ഇൻസാൻ മുർസലാത്ത് നബഅ് നാസിആത്ത് അബസ തക്വീർ ഇൻഫിതാർ മുത്വഫ്ഫിഫീൻ ഇൻശിഖാഖ് ബുറൂജ് ത്വാരിഖ് അഅ്‌ല ഗാശിയ ഫജ്റ് ബലദ് ശംസ് ലൈൽ ദുഹാ ശർഹ് തീൻ അലഖ് ഖദ്റ് ബയ്യിന സൽസല ആദിയാത്ത് ഖാരിഅ തകാസുർ അസ്റ് ഹുമസ ഫീൽ ഖുറൈശ് മാഊൻ കൗസർ കാഫിറൂൻ നസ്റ് മസദ് ഇഖ്‌ലാസ് ഫലഖ് നാസ്""".split()
if len(MALAYALAM_NAMES) != 114:
    raise RuntimeError("Expected Malayalam transliterations for all 114 surahs")


def normalize_arabic(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[\u064b-\u065f\u0670\u06d6-\u06ed\u0640]", "", text)
    text = re.sub(r"[إأآٱ]", "ا", text).replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي")
    return re.findall(r"[\u0621-\u064a]+", text)


def compare_recitation(expected: str, transcript: str) -> list[int]:
    reference = normalize_arabic(expected)
    heard = normalize_arabic(transcript)
    if not heard:
        return list(range(len(reference)))
    diff = SequenceMatcher(None, reference, heard, autojunk=False)
    wrong = []
    for tag, a, b, _, _ in diff.get_opcodes():
        if tag == "equal":
            continue
        wrong.extend(range(a, b))
        if tag == "insert" and reference:
            wrong.append(min(a, len(reference) - 1))
    return sorted(set(wrong))
