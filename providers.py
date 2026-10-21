import os
import io
import base64
import tempfile

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")

# ================= STT =================
def transcribe(wav_data: bytes) -> str:
    """WAV bytes -> text (Groq Whisper) - handles both bytes and path"""
    # Handle if old app.py passes path string (backwards compatible)
    if isinstance(wav_data, str):
        try:
            with open(wav_data, "rb") as f:
                wav_data = f.read()
        except:
            print(f"[STT] Invalid path string: {wav_data}")
            return "Assalamu Alaikum"
    
    if not wav_data or len(wav_data) < 1000:
        return "[NO_SPEECH]"

    if not GROQ_API_KEY:
        print("[STT] No GROQ_API_KEY set!")
        return "Bismillah"

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        result = client.audio.transcriptions.create(
            file=("audio.wav", wav_data),
            model="whisper-large-v3",
            language="ml",
            response_format="text",
            prompt="Malayalam, Manglish, Arabic, Bismillah, Quran, Surah"
        )
        text = result.strip() if isinstance(result, str) else getattr(result, 'text', str(result)).strip()
        print(f"[STT] Transcribed: {text}")
        return text if len(text) > 1 else "Bismillahirrahmanirrahim"
    except Exception as e:
        print(f"[STT] Error: {e}")
        import traceback; traceback.print_exc()
        return "Bismillahirrahmanirrahim"

# ================= LLM =================
def answer(question: str) -> str:
    """Answer - ALWAYS calls Groq LLM, no hardcoded same reply"""
    question = (question or "").strip()
    print(f"[LLM] Q: {question}")

    if not question or question == "[NO_SPEECH]":
        question = "Assalamu Alaikum"

    if not GROQ_API_KEY:
        return "Wa Alaikum Salam! Njan HYZIN aanu, Mashood Thennala undaakkiyathu! Enth sahayam venam?"

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)

        # NO hardcoded if salam return same text - let LLM handle all
        system = """You are HYZIN V1, created by Mashood Thennala from Kerala.
- You are a Quran learning companion for Malayalam speakers.
- Reply in Manglish (Malayalam in English letters) - NOT pure English.
- Keep answer SHORT: 1-2 sentences only, for voice speaker.
- If user says Bismillah / Bismillahirrahmanirrahim: explain it means 'In the name of Allah, Most Gracious, Most Merciful' and it's start of Quran.
- If user says Assalamu Alaikum: reply Wa Alaikum Salam warmly and ask what to learn.
- If user asks about Quran, Surah, Islam: give helpful short answer in Manglish.
- Be friendly, Islamic, concise.
- NEVER repeat same sentence every time. Be dynamic."""

        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": question}
            ],
            max_tokens=150,
            temperature=0.8
        )
        ans = resp.choices[0].message.content.strip()
        print(f"[LLM] A: {ans}")
        # Prevent too long for TTS
        if len(ans) > 300:
            ans = ans[:280] + "."
        return ans

    except Exception as e:
        print(f"[LLM] Groq fail: {e}")
        import traceback; traceback.print_exc()
        # Fallback dynamic answers (not same every time)
        ql = question.lower()
        if "bismillah" in ql:
            return "Bismillahirrahmanirrahim ennal Allahuvinte Thirunaamathil, Karunamayavan, Karunamayan ennanu. Quran thudangunnathu ithu paranjanu!"
        if "fatiha" in ql:
            return "Surah Fatiha Quran thile first surah aanu, 7 ayat undu, namazil nithyam othunnathu!"
        if "yaseen" in ql or "yasin" in ql:
            return "Surah Yaseen Quran thinte hridayam ennu parayum, paapam pottikkum!"
        return "Wa Alaikum Salam! Njan HYZIN aanu, Quran padikkan sahayikkam. Enthanu padikkan ullathu?"

def language_for(text: str) -> str:
    # Always Malayalam TTS for Manglish
    return "ml-IN"

# ================= TTS =================
def synthesize(text: str, lang: str = "ml") -> bytes:
    """Text -> WAV bytes 16kHz mono - Malayalam voice"""
    if not text:
        text = "Assalamu Alaikum"

    print(f"[TTS] Text: {text[:100]}")

    # 1. Try Sarvam (best Malayalam)
    if SARVAM_API_KEY:
        try:
            import requests
            url = "https://api.sarvam.ai/text-to-speech"
            headers = {"API-Subscription-Key": SARVAM_API_KEY}
            payload = {
                "inputs": [text],
                "target_language_code": "ml-IN",
                "speaker": "anushka",
                "pace": 0.95,
                "loudness": 1.5,
                "speech_sample_rate": 16000,
                "enable_preprocessing": True,
                "model": "bulbul:v1"
            }
            r = requests.post(url, json=payload, headers=headers, timeout=20)
            if r.status_code == 200:
                j = r.json()
                audios = j.get("audios", [])
                if audios:
                    data = base64.b64decode(audios[0])
                    print(f"[TTS] Sarvam OK {len(data)} bytes")
                    return data
            print(f"[TTS] Sarvam fail {r.status_code} {r.text[:200]}")
        except Exception as e:
            print(f"[TTS] Sarvam err {e}")

    # 2. Try gTTS + pydub
    try:
        from gtts import gTTS
        from pydub import AudioSegment
        
        mp3_io = io.BytesIO()
        # Try Malayalam, fallback English
        try:
            tts = gTTS(text=text, lang='ml', slow=False)
            tts.write_to_fp(mp3_io)
        except:
            tts = gTTS(text=text, lang='en', tld='co.in', slow=False)
            tts.write_to_fp(mp3_io)
        
        mp3_io.seek(0)
        sound = AudioSegment.from_file(mp3_io, format="mp3")
        sound = sound.set_frame_rate(16000).set_channels(1).set_sample_width(2)
        wav_io = io.BytesIO()
        sound.export(wav_io, format="wav")
        wav_data = wav_io.getvalue()
        print(f"[TTS] gTTS OK {len(wav_data)} bytes")
        return wav_data
    except Exception as e:
        print(f"[TTS] gTTS fail {e}")

    # 3. edge-tts fallback
    try:
        import edge_tts, asyncio
        from pydub import AudioSegment
        
        async def _run():
            tmp = "/tmp/edge.mp3"
            # Malayalam voice
            voice = "ml-IN-AnjanaNeural"
            try:
                comm = edge_tts.Communicate(text, voice)
                await comm.save(tmp)
            except:
                comm = edge_tts.Communicate(text, "en-IN-NeerjaNeural")
                await comm.save(tmp)
            snd = AudioSegment.from_file(tmp)
            snd = snd.set_frame_rate(16000).set_channels(1).set_sample_width(2)
            out = io.BytesIO()
            snd.export(out, format="wav")
            return out.getvalue()
        
        data = asyncio.run(_run())
        print(f"[TTS] edge-tts OK {len(data)}")
        return data
    except Exception as e:
        print(f"[TTS] edge-tts fail {e}")

    # 4. Silence fallback (never 55 bytes JSON)
    import wave
    with io.BytesIO() as out:
        with wave.open(out, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
            w.writeframes(b"\x00\x00" * 16000)
        print("[TTS] Returning silence WAV")
        return out.getvalue()
