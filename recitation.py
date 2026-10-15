"""Fixed-host Husary Muallim MP3 download and offline decode to canonical WAV."""
import io
import subprocess
import wave
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "data" / "audio-cache"
BASE = "https://everyayah.com/data/Husary_Muallim_128kbps"


def recitation(surah: int, ayah: int, slow: bool = False) -> bytes:
    name = f"{surah:03}{ayah:03}"
    cache_file = CACHE / f"{name}{'-slow' if slow else ''}.wav"
    if cache_file.exists():
        return cache_file.read_bytes()
    mp3 = CACHE / f"{name}.mp3"
    CACHE.mkdir(parents=True, exist_ok=True)
    if not mp3.exists():
        with httpx.Client(timeout=35) as client:
            with client.stream("GET", f"{BASE}/{name}.mp3") as response:
                response.raise_for_status()
                if response.headers.get("content-type", "").split(";")[0] not in ("audio/mpeg", "audio/mp3"):
                    raise ValueError("Unexpected recitation content type")
                chunks = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > 3_000_000:
                        raise ValueError("Recitation file too large")
                    chunks.append(chunk)
        mp3.write_bytes(b"".join(chunks))
    # ffmpeg writes RAW PCM; Python wave makes a fixed 44-byte header for ESP32.
    command = ["ffmpeg", "-v", "error", "-nostdin", "-f", "mp3", "-i", "pipe:0"]
    if slow:
        command += ["-af", "atempo=0.75"]
    command += ["-ac", "1", "-ar", "16000", "-acodec", "pcm_s16le", "-f", "s16le", "pipe:1"]
    decoded = subprocess.run(command, input=mp3.read_bytes(), stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, timeout=90, check=True)
    if not 0 < len(decoded.stdout) <= 16000 * 2 * 300 or len(decoded.stdout) % 2:
        raise ValueError("Recitation duration unsupported")
    with io.BytesIO() as output:
        with wave.open(output, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(decoded.stdout)
        audio = output.getvalue()
    cache_file.write_bytes(audio)
    return audio
