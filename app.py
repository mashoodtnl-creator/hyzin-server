import io
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
TTL_SECONDS = 600  # Increased from 180 to 600 sec
MAX_WAV_BYTES = 44 + 16000 * 2 * 8

# Ensure audio dir exists
os.makedirs("audio", exist_ok=True)

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
        # Also delete disk file
        try:
            p = f"audio/{k}.wav"
            if os.path.exists(p):
                os.remove(p)
        except:
            pass

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
        print(f"[TALK] TTS returned {len(audio_bytes) if audio_bytes else 0} bytes")
    except Exception as e:
        print(f"[TALK] TTS failed: {e}")
        import traceback
        traceback.print_exc()
        audio_bytes = _make_silence_wav(800)

    if not audio_bytes or len(audio_bytes) < 100:
        print(f"[TALK] Audio too small ({len(audio_bytes) if audio_bytes else 0}), using silence")
        audio_bytes = _make_silence_wav(800)

    audio_id = uuid.uuid4().hex
    _audio[audio_id] = (time.time(), audio_bytes, answer_text.encode("utf-8"))
    
    # CRITICAL FIX: Save to disk too! Survives memory clear & Render spin-down
    try:
        disk_path = f"audio/{audio_id}.wav"
        with open(disk_path, "wb") as f:
            f.write(audio_bytes)
        print(f"[TALK] Saved audio to {disk_path} - {len(audio_bytes)} bytes")
    except Exception as e:
        print(f"[TALK] Disk save failed: {e}")
    
    if len(_audio) > 50:
        _audio.popitem(last=False)

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
    
    # 1. Check memory first (fastest)
    entry = _audio.get(key)
    if entry:
        _, audio_bytes, _ = entry
        print(f"[AUDIO] Serving {key} from MEMORY - {len(audio_bytes)} bytes")
        return Response(content=audio_bytes, media_type="audio/wav")
    
    # 2. Check disk (survives Render spin-down & memory clear)
    disk_path = f"audio/{key}.wav"
    if os.path.exists(disk_path):
        try:
            with open(disk_path, "rb") as f:
                data = f.read()
            print(f"[AUDIO] Serving {key} from DISK - {len(data)} bytes")
            # Put back in memory for next time
            _audio[key] = (time.time(), data, b"")
            return Response(content=data, media_type="audio/wav")
        except Exception as e:
            print(f"[AUDIO] Disk read failed: {e}")
    
    # 3. CRITICAL: Don't return 404 JSON (55 bytes bug)! Return silence WAV
    print(f"[AUDIO] NOT FOUND {key} - returning silence WAV (not 404 JSON)")
    silence = _make_silence_wav(800)
    return Response(content=silence, media_type="audio/wav")

@app.get("/")
async def root():
    return {"status": "HYZIN V2 Live", "version": "fixed-audio-persist"}

@app.get("/health")
async def health():
    return {"ok": True}
    
import os
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
