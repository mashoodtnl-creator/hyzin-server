
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

load_dotenv()
app = FastAPI(title="HYZIN V2 Quran learning API")
_audio: OrderedDict[str, tuple[float, bytes, bytes]] = OrderedDict()
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

def _make_silence_wav(duration_ms: int = 800) -> bytes:
    samples = int(16000 * duration_ms / 1000)
    with io.BytesIO() as out:
        with wave.open(out, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(b"\x00\x00" * samples)
        return out.getvalue()

def _cleanup():
    now = time.time()
    expired = [k for k, (t, _, _) in _audio.items() if now - t > TTL_SECONDS]
    for k in expired:
        _audio.pop(k, None)

@app.post("/talk")
async def talk(request: Request, x_device_token: str | None = Header(default=None)):
    check_token(x_device_token)
    _cleanup()
    wav_data = await limited_body(request)
    validate_wav(wav_data)

    try:
        transcript = await run_in_threadpool(providers.transcribe, wav_data)
    except Exception as e:
        print(f"[TALK] transcribe failed: {e}")
        transcript = "[NO_SPEECH]"

    if not transcript or transcript == "[NO_SPEECH]":
        transcript = "Assalamu Alaikum"

    try:
        answer_text = await run_in_threadpool(providers.answer, transcript)
    except Exception as e:
        print(f"[TALK] answer failed: {e}")
        answer_text = "Wa Alaikum Assalam! I am HYZIN, how can I help you learn today?"

    try:
        lang = providers.language_for(answer_text)
    except Exception:
        lang = "en-IN"

    audio_bytes = None
    try:
        audio_bytes = await run_in_threadpool(providers.synthesize, answer_text, lang)
    except Exception as e:
        print(f"[TALK] TTS failed: {e}")
        audio_bytes = _make_silence_wav(800)

    if not audio_bytes:
        audio_bytes = _make_silence_wav(800)

    audio_id = uuid.uuid4().hex
    _audio[audio_id] = (time.time(), audio_bytes, answer_text.encode("utf-8"))
    if len(_audio) > 50:
        _audio.popitem(last=False)

    # DO NOT return raw bytes in JSON - return None for display
    return {
        "text": answer_text,
        "lang": lang,
        "audio_url": f"/audio/{audio_id}.wav",
        "display_url": None,
        "transcript": transcript,
    }

@app.get("/audio/{audio_id}.wav")
async def get_audio(audio_id: str):
    _cleanup()
    key = audio_id.replace(".wav", "")
    entry = _audio.get(key)
    if not entry:
        raise HTTPException(404, "Audio not found")
    _, audio_bytes, _ = entry
    return Response(content=audio_bytes, media_type="audio/wav")

@app.get("/")
async def root():
    return {"status": "HYZIN V2 Live", "version": "fixed-500"}

@app.get("/health")
async def health():
    return {"ok": True}
