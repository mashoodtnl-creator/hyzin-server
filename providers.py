import os
import io
import tempfile
from pathlib import Path

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")

# ---------- STT ----------
def transcribe(wav_bytes: bytes) -> str:
    """Transcribe WAV bytes -> text using Groq Whisper"""
    if not wav_bytes or len(wav_bytes) < 1000:
        print("[STT] WAV too small")
        return "[NO_SPEECH]"
    
    if not GROQ_API_KEY:
        print("[STT] No GROQ_API_KEY")
        return "[NO_SPEECH]"
    
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        
        # Groq expects file-like: (filename, bytes)
        transcription = client.audio.transcriptions.create(
            file=("audio.wav", wav_bytes),
            model="whisper-large-v3",
            language="ml",  # Malayalam + English auto
            response_format="text",
            prompt="Malayalam, Manglish, English, Arabi Malayalam"
        )
        
        # Response can be str or object
        if isinstance(transcription, str):
            text = transcription.strip()
        else:
            text = getattr(transcription, 'text', str(transcription)).strip()
        
        print(f"[STT] Success: {text}")
        if len(text) < 2:
            return "[NO_SPEECH]"
        return text
        
    except Exception as e:
        print(f"[STT] Groq error: {e}")
        import traceback
        traceback.print_exc()
        return "[NO_SPEECH]"

# ---------- LLM ANSWER ----------
def answer(question: str) -> str:
    """Answer using Groq LLM - no more same greeting"""
    question = (question or "").strip()
    print(f"[LLM] Question: {question}")
    
    if not question or question == "[NO_SPEECH]":
        question = "Assalamu Alaikum"
    
    # If no key, fallback
    if not GROQ_API_KEY:
        if "salam" in question.lower():
            return "Wa Alaikum Salam! Njan HYZIN aanu, enthu sahayam venam?"
        return f"You said: {question}. I am HYZIN!"
    
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        
        system_prompt = """You are HYZIN, a friendly Malayalam Quran learning companion.
- Reply in Manglish (Malayalam in English letters) if user speaks Malayalam/Manglish.
- Keep answers short (1-2 sentences) for voice.
- Be helpful about Quran, Islam, general knowledge.
- If user says Salam, reply Salam and ask how to help.
- Don't repeat same greeting every time, be conversational."""

        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            max_tokens=200,
            temperature=0.7
        )
        ans = resp.choices[0].message.content.strip()
        print(f"[LLM] Answer: {ans}")
        return ans
        
    except Exception as e:
        print(f"[LLM] Groq error: {e}")
        import traceback
        traceback.print_exc()
        return "Wa Alaikum Salam! Njan HYZIN aanu, enthu sahayam venam?"

def language_for(text: str) -> str:
    # Simple detection: if Malayalam chars or manglish pattern, use ml
    # gTTS uses ml for Malayalam
    lower = text.lower()
    # If contains malayalam english mix, still use en but gtts will handle
    return "ml"

# ---------- TTS ----------
def synthesize(text: str, lang: str = "ml") -> bytes:
    """TTS text -> WAV bytes (16kHz mono)"""
    if not text:
        text = "Hello"
    
    print(f"[TTS] Synthesizing: {text[:80]} lang={lang}")
    
    # Try Sarvam if available (best Malayalam)
    if SARVAM_API_KEY:
        try:
            import requests
            url = "https://api.sarvam.ai/text-to-speech"
            headers = {"API-Subscription-Key": SARVAM_API_KEY}
            payload = {
                "inputs": [text],
                "target_language_code": "ml-IN",
                "speaker": "anushka",
                "pitch": 0,
                "pace": 1.0,
                "loudness": 1.0,
                "speech_sample_rate": 16000,
                "enable_preprocessing": True,
                "model": "bulbul:v1"
            }
            r = requests.post(url, json=payload, headers=headers, timeout=15)
            if r.status_code == 200:
                data = r.json()
                import base64
                audios = data.get("audios", [])
                if audios:
                    wav_bytes = base64.b64decode(audios[0])
                    print(f"[TTS] Sarvam success {len(wav_bytes)} bytes")
                    return wav_bytes
            print(f"[TTS] Sarvam failed: {r.text[:200]}")
        except Exception as e:
            print(f"[TTS] Sarvam error: {e}")
    
    # Fallback: gTTS -> MP3 -> WAV (16kHz mono) using audioop-lts
    try:
        from gtts import gTTS
        import io
        
        # gTTS language: ml for Malayalam, en for English
        tts_lang = "ml" if lang.startswith("ml") else "en"
        if tts_lang == "ml":
            # gTTS may not support ml, try en
            try:
                mp3_fp = io.BytesIO()
                tts = gTTS(text=text, lang='ml', slow=False)
                tts.write_to_fp(mp3_fp)
            except:
                mp3_fp = io.BytesIO()
                tts = gTTS(text=text, lang='en', slow=False)
                tts.write_to_fp(mp3_fp)
        else:
            mp3_fp = io.BytesIO()
            tts = gTTS(text=text, lang='en', slow=False)
            tts.write_to_fp(mp3_fp)
        
        mp3_fp.seek(0)
        mp3_bytes = mp3_fp.read()
        print(f"[TTS] gTTS MP3 {len(mp3_bytes)} bytes")
        
        # Convert MP3 to WAV 16kHz mono using pydub
        try:
            from pydub import AudioSegment
            # Ensure audioop-lts provides audioop
            import audioop
            mp3_fp.seek(0)
            sound = AudioSegment.from_file(mp3_fp, format="mp3")
            sound = sound.set_frame_rate(16000).set_channels(1).set_sample_width(2)
            wav_io = io.BytesIO()
            sound.export(wav_io, format="wav")
            wav_bytes = wav_io.getvalue()
            print(f"[TTS] Converted to WAV {len(wav_bytes)} bytes")
            return wav_bytes
        except Exception as e:
            print(f"[TTS] pydub convert failed: {e}, returning MP3 as is wrapped in WAV header?")
            # Last resort: return MP3 bytes but wrap? ESP32 expects WAV, so create silence + return?
            # Actually return mp3 wrapped - better return a valid WAV of silence + log
            # Try simple: if mp3 fails, use edge-tts
            raise e
            
    except Exception as e:
        print(f"[TTS] gTTS failed: {e}")
    
    # Last fallback: edge-tts (direct WAV)
    try:
        import edge_tts
        import asyncio
        
        async def _edge_tts():
            tmp_path = "/tmp/edge.wav"
            # Choose voice based on lang
            voice = "ml-IN-AnjanaNeural" if lang.startswith("ml") else "en-IN-NeerjaNeural"
            try:
                comm = edge_tts.Communicate(text, voice)
                await comm.save(tmp_path)
            except:
                comm = edge_tts.Communicate(text, "en-US-AriaNeural")
                await comm.save(tmp_path)
            
            # Convert to 16kHz mono if needed
            try:
                from pydub import AudioSegment
                sound = AudioSegment.from_file(tmp_path)
                sound = sound.set_frame_rate(16000).set_channels(1).set_sample_width(2)
                wav_io = io.BytesIO()
                sound.export(wav_io, format="wav")
                return wav_io.getvalue()
            except:
                with open(tmp_path, "rb") as f:
                    return f.read()
        
        wav_bytes = asyncio.run(_edge_tts())
        print(f"[TTS] edge-tts success {len(wav_bytes)} bytes")
        return wav_bytes
        
    except Exception as e:
        print(f"[TTS] edge-tts failed: {e}")
    
    # Ultimate fallback: silence WAV 1 sec
    print("[TTS] All TTS failed, returning silence")
    import wave
    with io.BytesIO() as out:
        with wave.open(out, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(b"\x00\x00" * 16000)
        return out.getvalue()
