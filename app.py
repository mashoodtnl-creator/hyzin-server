"""Private-LAN HYZIN speech API: 16k mono PCM WAV in, text + audio URL out."""
import io
import hashlib
import os
import secrets
import time
import uuid
import wave
from collections import OrderedDict

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response

import providers
import intent
import quran_flow
from display_render import render_reply

load_dotenv()
app = FastAPI(title="HYZIN V2 Quran learning API")
_audio: OrderedDict[str, tuple[float, bytes, bytes]] = OrderedDict()
_sessions: dict[str, quran_flow.Session] = {}
TTL_SECONDS = 180
MAX_WAV_BYTES = 44 + 16000 * 2 * 8


def check_token(token: str | None) -> None:
    expected = os.environ.get("HYZIN_DEVICE_TOKEN", "")
    if not expected or not token or not secrets.compare_digest(expected, token):
        raise HTTPException(401, "Unauthorized")


def validate_wav(data: bytes, max_seconds: int = 8) -> None:
    limit = 44 + 16000 * 2 * max_seconds
    if len(data) < 44 or len(data) > limit:
        raise HTTPException(400, "WAV duration/size invalid")
    try:
        with wave.open(io.BytesIO(data), "rb") as wav:
            if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != 16000:
                raise HTTPException(400, "Expected 16kHz mono 16-bit PCM")
            if wav.getcomptype() != "NONE" or wav.getnframes() < 8000:
                raise HTTPException(400, "Too short or compressed WAV")
            if wav.getnframes() * 2 + 44 > limit:
                raise HTTPException(400, "WAV is too long")
            if len(wav.readframes(wav.getnframes())) != wav.getnframes() * 2:
                raise HTTPException(400, "Truncated WAV")
    except (EOFError, wave.Error) as exc:
        raise HTTPException(400, "Invalid WAV") from exc


async def limited_body(request: Request) -> bytes:
    chunks = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_WAV_BYTES:
            raise HTTPException(413, "Recording too large")
        chunks.append(chunk)
    return b"".join(chunks)


def remember_audio(data: bytes, display: bytes) -> str:
    now = time.monotonic()
    for key, (created, _, _) in list(_audio.items()):
        if now - created > TTL_SECONDS:
            del _audio[key]
    while len(_audio) >= 8:
        _audio.popitem(last=False)
    key = uuid.uuid4().hex
    _audio[key] = (now, data, display)
    return key


@app.post("/talk")
async def talk(request: Request, x_device_token: str | None = Header(default=None)) -> dict[str, str]:
    check_token(x_device_token)
    if request.headers.get("content-type", "").split(";")[0].strip() != "audio/wav":
        raise HTTPException(415, "Content-Type must be audio/wav")
    data = await limited_body(request)
    validate_wav(data)
    session_id = hashlib.sha256(x_device_token.encode()).hexdigest()
    active = _sessions.get(session_id)
    try:
        if active and active.awaiting_recitation:
            result = await run_in_threadpool(quran_flow.handle_recitation, active, data)
            text, audio, display = result.text, result.audio, result.display
            mood = result.mood
        else:
            transcript = await run_in_threadpool(providers.transcribe, data)
            if not transcript or transcript == "[NO_SPEECH]":
                raise HTTPException(422, "No clear speech detected")
            command = intent.parse(transcript)
            if command is None and intent.looks_quran_related(transcript):
                command = await run_in_threadpool(intent.fallback, transcript)
            if command:
                result, state = await run_in_threadpool(quran_flow.handle_command, command, active)
                _sessions[session_id] = state
                text, audio, display = result.text, result.audio, result.display
                mood = result.mood
            else:
                if intent.looks_quran_related(transcript):
                    text = "സൂറത്തിന്റെ പേരും ആയത്ത് നമ്പറും പറഞ്ഞാൽ ഉറവിടത്തിൽ നിന്ന് കേൾപ്പിക്കാം."
                else:
                    text = await run_in_threadpool(providers.answer, transcript)
                if not text:
                    raise HTTPException(502, "Empty answer from provider")
                audio = await run_in_threadpool(providers.synthesize, text, providers.language_for(transcript))
                display = await run_in_threadpool(render_reply, text, providers.language_for(transcript))
                mood = "happy"
    except (ValueError, FileNotFoundError) as exc:
        # Do not silently fall back to LLM text when scripture or reference is unavailable.
        raise HTTPException(422, str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"ERROR: {exc}")
        raise HTTPException(502, "Speech or Quran audio source unavailable") from exc
    validate_wav(audio, max_seconds=300)
    key = remember_audio(audio, display)
    return {"text": text, "audio_url": f"/audio/{key}",
            "display_url": f"/display/{key}", "mood": mood,
            "display_format": "rgb565" if len(display) == 128 * 160 * 2 else "mono"}


@app.get("/audio/{key}")
def get_audio(key: str, x_device_token: str | None = Header(default=None)) -> Response:
    check_token(x_device_token)
    cached = _audio.get(key)
    if not cached or time.monotonic() - cached[0] > TTL_SECONDS:
        _audio.pop(key, None)
        raise HTTPException(404, "Audio expired")
    return Response(cached[1], media_type="audio/wav")


@app.get("/display/{key}")
def get_display(key: str, x_device_token: str | None = Header(default=None)) -> Response:
    check_token(x_device_token)
    cached = _audio.get(key)
    if not cached or time.monotonic() - cached[0] > TTL_SECONDS:
        _audio.pop(key, None)
        raise HTTPException(404, "Display expired")
    return Response(cached[2], media_type="application/octet-stream")
