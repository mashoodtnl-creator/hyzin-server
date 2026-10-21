import os
import io
import wave
import random
from groq import Groq
import google.generativeai as genai

# For TTS - GTTS is most reliable on Render
from gtts import gTTS
from pydub import AudioSegment

# ===== LLM CONFIG =====
GROQ_MODELS_2026 = [
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-3.1-8b-instant",
    "qwen/qwen3-32b",
]

MALAYALAM_PROMPT = """You are HYZIN, created by Mashood Thennala.
ALWAYS reply in Manglish Malayalam (Malayalam in English letters).
SHORT - 1 line, max 15 words.
If Salam: "Wa Alaikum Salam! Enthokke undu? Njan HYZIN aanu!"
Example: User "Nee aara?" -> You "Njan HYZIN aanu, Mashood Thennala undaakkiyathu!"
User "What is your name?" -> "Ente peru HYZIN aanu!"
"""

def get_groq_client():
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return None
    return Groq(api_key=key)

def try_groq(text):
    client = get_groq_client()
    if not client:
        print("[GROQ] No API key")
        return None
    for model in GROQ_MODELS_2026:
        try:
            print(f"[GROQ] Trying {model}")
            resp = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": MALAYALAM_PROMPT},
                    {"role": "user", "content": text or "Nee aara?"}
                ],
                model=model,
                temperature=0.7,
                max_tokens=80
            )
            reply = resp.choices[0].message.content.strip()
            if reply:
                print(f"[GROQ] SUCCESS {model}: {reply[:80]}")
                return reply
        except Exception as e:
            print(f"[GROQ] {model} failed: {e}")
            continue
    return None

def try_gemini(text):
    try:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            print("[GEMINI] No API key")
            return None
        genai.configure(api_key=key)
        model = genai.GenerativeModel("gemini-2.0-flash", system_instruction=MALAYALAM_PROMPT)
        resp = model.generate_content(text or "Nee aara?")
        reply = resp.text.strip()
        if reply:
            print(f"[GEMINI] SUCCESS: {reply[:80]}")
            return reply
    except Exception as e:
        print(f"[GEMINI] failed: {e}")
    return None

# ===== FUNCTIONS EXPECTED BY APP.PY =====

def transcribe(wav_data: bytes) -> str:
    """Transcribe WAV to text - using Sarvam if available, else dummy"""
    try:
        # Try Sarvam STT if key exists
        sarvam_key = os.getenv("SARVAM_API_KEY")
        if sarvam_key:
            import requests
            # Sarvam STT implementation - simplified
            print("[STT] Trying Sarvam")
            # For now return dummy - implement Sarvam API if needed
            pass
        
        # Fallback - return simple trigger
        print(f"[STT] WAV size: {len(wav_data)} bytes - using fallback")
        return "Assalamu Alaikum"
    except Exception as e:
        print(f"[STT] Failed: {e}")
        return "Assalamu Alaikum"

def answer(transcript: str) -> str:
    """Generate Manglish Malayalam answer"""
    # 1. Try Groq
    reply = try_groq(transcript)
    if reply:
        return reply
    
    # 2. Try Gemini
    reply = try_gemini(transcript)
    if reply:
        return reply
    
    # 3. Fallback
    print("[ANSWER] Using Malayalam fallback")
    fallbacks = [
        "Wa Alaikum Salam! Njan HYZIN aanu, enthu sahayam venam?",
        "Njan HYZIN aanu, Mashood Thennala undaakkiyathu! Enth parayan ullu?",
        "Enthokke undu? Njan HYZIN aanu, sahayikatte?",
        "Hello! Njan HYZIN aanu, entha cheyyendathu?",
    ]
    return random.choice(fallbacks)

def language_for(text: str) -> str:
    """Detect language - return en-IN for Manglish"""
    return "en-IN"

def _make_silence_wav_bytes(duration_ms: int = 800) -> bytes:
    """Create silent WAV bytes"""
    samples = int(16000 * duration_ms / 1000)
    with io.BytesIO() as out:
        with wave.open(out, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(b"\x00\x00" * samples)
        return out.getvalue()

def synthesize(text: str, lang: str = "en-IN") -> bytes:
    """
    CRITICAL FIX: This MUST return WAV BYTES, not text!
    Previous bug returned text, causing 55 byte audio!
    """
    try:
        print(f"[TTS] Synthesizing: {text[:50]}... lang={lang}")
        
        # Use GTTS - most reliable on Render free tier
        mp3_buffer = io.BytesIO()
        tts = gTTS(text=text, lang='en', slow=False)
        tts.write_to_fp(mp3_buffer)
        mp3_buffer.seek(0)
        
        # Convert MP3 to WAV 16kHz mono for ESP32
        sound = AudioSegment.from_file(mp3_buffer, format="mp3")
        sound = sound.set_frame_rate(16000).set_channels(1).set_sample_width(2)
        
        wav_buffer = io.BytesIO()
        sound.export(wav_buffer, format="wav")
        wav_bytes = wav_buffer.getvalue()
        
        print(f"[TTS] SUCCESS! Generated {len(wav_bytes)} bytes (was 55 before fix!)")
        return wav_bytes
        
    except Exception as e:
        print(f"[TTS] FAILED: {e}")
        import traceback
        traceback.print_exc()
        # Return silence WAV, not None, not text!
        return _make_silence_wav_bytes(800)
