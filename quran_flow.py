"""Server-side session logic for playback and a cautious word check."""
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import intent
import providers
import quran
import recitation
from display_render import render_ayah, render_reply


@dataclass
class Session:
    surah: int
    ayah: int
    awaiting_recitation: bool = False


@dataclass
class Result:
    text: str
    audio: bytes
    display: bytes
    mood: str = "happy"


def _say(text: str, display: bytes) -> Result:
    return Result(text, providers.synthesize(text, "ml-IN"), display)


def handle_recitation(session: Session, wav: bytes) -> Result:
    verse = quran.get_ayah(session.surah, session.ayah)
    session.awaiting_recitation = False
    spoken = providers.transcribe_arabic(wav)
    if not quran.normalize_arabic(spoken):
        message = "ഓത്ത് വ്യക്തമായില്ല. വീണ്ടും ശ്രമിക്കൂ; ഉസ്താദിനോട് ഉറപ്പാക്കൂ."
        return _say(message, render_ayah(verse))
    wrong = quran.compare_recitation(verse.arabic, spoken)
    if wrong:
        words = [w for w in verse.arabic.split() if quran.normalize_arabic(w)]
        target = words[wrong[0]] if wrong[0] < len(words) else words[0]
        message = f"{target} എന്ന വാക്ക് വീണ്ടും ഓതൂ. ഇത് ഏകദേശ പരിശോധനയാണ്; ഉസ്താദിനോട് ഉറപ്പാക്കൂ."
        return _say(message, render_ayah(verse, wrong))
    message = "വാക്കുകൾ യോജിക്കുന്നതുപോലെ തോന്നുന്നു. തജ്‌വീദ് പരിശോധിച്ചിട്ടില്ല; ഉസ്താദിനോട് ഉറപ്പാക്കൂ."
    return _say(message, render_ayah(verse))


def handle_command(command: intent.Intent, current: Session | None) -> tuple[Result, Session]:
    # Curated reference-only picks; verses and translations ALWAYS come from the corpus.
    daily = {"daily_ayah": ((1, 1), (112, 1), (94, 5), (20, 114)),
             "daily_dua": ((2, 201), (20, 114), (3, 8))}
    if command.action in daily:
        picks = daily[command.action]
        selected = picks[datetime.now(ZoneInfo("Asia/Kolkata")).toordinal() % len(picks)]
        command = intent.Intent("play", *selected)
    surah = command.surah if command.surah is not None else current.surah if current else None
    if surah is None:
        raise ValueError("ആദ്യം സൂറത്തിന്റെ പേര് പറയൂ (ഉദാ: സൂറത്ത് ഫാതിഹ ഓതൂ).")
    ayah = command.ayah if command.ayah is not None else (current.ayah if current and current.surah == surah else 1)
    if command.action == "next":
        ayah += 1
    elif command.action == "previous":
        ayah -= 1
    verse = quran.get_ayah(surah, ayah)
    state = Session(surah, ayah)
    if command.action == "check":
        state.awaiting_recitation = True
        prompt = "ഇപ്പോൾ ഈ ആയത്ത് ഓതൂ; വാക്കുകൾ ഏകദേശമായി പരിശോധിക്കാം. ഉസ്താദിനോട് ഉറപ്പാക്കൂ."
        return _say(prompt, render_ayah(verse)), state
    return Result(f"സൂറത്ത് {surah}, ആയത്ത് {ayah}.",
                  recitation.recitation(surah, ayah, slow=command.action == "slow"),
                  render_ayah(verse)), state
