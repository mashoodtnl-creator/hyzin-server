import os
import io
import base64
import requests

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")

# Surah name -> number map for recitation
SURAH_MAP = {
    "fatiha": 1, "fathih": 1, "al-fatiha": 1,
    "baqarah": 2, "baqara": 2,
    "imran": 3, "ali imran": 3,
    "nisa": 4, "maida": 5, "anam": 6,
    "araf": 7, "anfal": 8, "tawbah": 9,
    "yunus": 10, "hud": 11, "yusuf": 12,
    "raad": 13, "ibrahim": 14, "hijr": 15,
    "nahl": 16, "isra": 17, "kahf": 18,
    "maryam": 19, "taha": 20, "anbiya": 21,
    "hajj": 22, "muminun": 23, "nur": 24,
    "furqan": 25, "shuara": 26, "naml": 27,
    "qasas": 28, "ankabut": 29, "rum": 30,
    "luqman": 31, "sajda": 32, "ahzab": 33,
    "saba": 34, "fatir": 35, "yaseen": 36, "yasin": 36, "ya-seen": 36,
    "saffat": 37, "sad": 38, "zumar": 39,
    "ghafir": 40, "fussilat": 41, "shura": 42,
    "zukhruf": 43, "dukhan": 44, "jathiya": 45,
    "ahqaf": 46, "muhammad": 47, "fath": 48,
    "hujurat": 49, "qaf": 50, "dhariyat": 51,
    "tur": 52, "najm": 53, "qamar": 54,
    "rahman": 55, "waqiah": 56, "hadid": 57,
    "mujadila": 58, "hashr": 59, "mumtahina": 60,
    "saff": 61, "jumua": 62, "munafiqun": 63,
    "taghabun": 64, "talaq": 65, "tahrim": 66,
    "mulk": 67, "qalam": 68, "haqqa": 69,
    "maarij": 70, "nuh": 71, "jinn": 72,
    "muzzammil": 73, "muddathir": 74, "qiyamah": 75,
    "insan": 76, "mursalat": 77, "naba": 78,
    "naziat": 79, "abasa": 80, "takwir": 81,
    "infitar": 82, "mutaffifin": 83, "inshiqaq": 84,
    "buruj": 85, "tariq": 86, "ala": 87, "ghashiya": 88,
    "fajr": 89, "balad": 90, "shams": 91, "lail": 92,
    "duha": 93, "sharha": 94, "tin": 95, "alaq": 96,
    "qadr": 97, "bayyina": 98, "zilzal": 99, "adiyat": 100,
    "qaria": 101, "takathur": 102, "asr": 103, "humaza": 104,
    "fil": 105, "quraish": 106, "maun": 107, "kawthar": 108,
    "kafirun": 109, "nasr": 110, "masad": 111,
    "ikhlas": 112, "falaq": 113, "nas": 114,
    "arafat": 0, "arafa": 0, "hajj": 0, "bismillah": 0
}

def _detect_surah(text: str) -> int:
    """Detect surah number from text, returns 0 if not Quran request"""
    low = text.lower()
    # Check if user wants Quran recitation
    quran_keywords = ["quran", "othu", "othi", "oathu", "recite", "tilawat", "surah", "surat", "sura", "para", "ayat", "qirat"]
    has_quran_intent = any(k in low for k in quran_keywords)
    
    # Also check surah names directly even without keyword
    for name, num in SURAH_MAP.items():
        if name in low and num > 0:
            print(f"[QURAN] Detected surah {name} -> {num}")
            return num
    
    # If has quran keyword but no surah name, default to Fatiha
    if has_quran_intent:
        print("[QURAN] Quran intent detected, defaulting to Fatiha")
        return 1
    
    return 0

# ================= STT =================
def transcribe(wav_data: bytes) -> str:
    if isinstance(wav_data, str):
        try:
            with open(wav_data, "rb") as f:
                wav_data = f.read()
        except:
            return "Assalamu Alaikum"
    
    if not wav_data or len(wav_data) < 1000:
        return "[NO_SPEECH]"

    if not GROQ_API_KEY:
        return "Surah Fatiha"

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        result = client.audio.transcriptions.create(
            file=("audio.wav", wav_data),
            model="whisper-large-v3",
            language="ml",
            response_format="text",
            prompt="Malayalam, Manglish, Quran, Surah Fatiha, Ikhlas, Yaseen, Bismillah, Arafat, Arabic"
        )
        text = result.strip() if isinstance(result, str) else getattr(result, 'text', str(result)).strip()
        print(f"[STT] {text}")
        return text if len(text) > 1 else "Assalamu Alaikum"
    except Exception as e:
        print(f"[STT] Error: {e}")
        return "Assalamu Alaikum"

# ================= LLM =================
def answer(question: str) -> str:
    question = (question or "").strip()
    print(f"[LLM] Q: {question}")
    if not question or question == "[NO_SPEECH]":
        question = "Assalamu Alaikum"

    # Check Quran recitation intent FIRST
    surah_num = _detect_surah(question)
    if surah_num > 0:
        surah_names = {1: "Fatiha", 2: "Baqarah", 36: "Yaseen", 112: "Ikhlas", 113: "Falaq", 114: "Nas"}
        sname = surah_names.get(surah_num, f"Surah {surah_num}")
        # Return special marker that app.py will detect for recitation
        return f"__QURAN_RECITE_{surah_num}__ {sname} othunnu. Bismillahirrahmanirrahim..."

    if not GROQ_API_KEY:
        ql = question.lower()
        if "bismillah" in ql:
            return "Bismillahirrahmanirrahim ennal Allahuvinte Thirunaamathil ennanu, Quran thudakkam!"
        if "arafat" in ql or "arafa" in ql:
            return "Arafat Hajj thile valiya divasam aanu, dua qabool aakum!"
        if "fatiha" in ql:
            return "__QURAN_RECITE_1__ Surah Fatiha othunnu"
        return "Wa Alaikum Salam! Njan HYZIN aanu, Quran padikkan sahayikkam!"

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        system = """You are HYZIN V1 by Mashood Thennala.
- Reply in Manglish short 1-2 lines.
- If user asks to recite Quran/Surah, reply EXACTLY: __QURAN_RECITE_{number}__ and then surah name.
  Example: user says 'Surah Fatiha odu' -> reply '__QURAN_RECITE_1__ Surah Fatiha'
  User says 'Ikhlas' -> '__QURAN_RECITE_112__ Surah Ikhlas'
  User says 'Yaseen' -> '__QURAN_RECITE_36__ Surah Yaseen'
- For other Islamic questions, answer in Manglish.
- Be dynamic, not same repeat."""

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
        return ans[:300]
    except Exception as e:
        print(f"[LLM] Fail {e}")
        if "fatiha" in question.lower():
            return "__QURAN_RECITE_1__ Surah Fatiha"
        return "Wa Alaikum Salam! Njan HYZIN aanu, enth padikkanam?"

def language_for(text: str) -> str:
    return "ml-IN"

# ================= TTS + QURAN RECITATION =================
def synthesize(text: str, lang: str = "ml") -> bytes:
    """If text contains __QURAN_RECITE_N__, fetch real Quran audio, else TTS"""
    print(f"[SYNTH] {text[:120]}")

    # Check Quran recitation marker
    import re
    match = re.search(r'__QURAN_RECITE_(\d+)__', text)
    if match:
        surah_num = int(match.group(1))
        print(f"[QURAN] Recitation requested for Surah {surah_num}")
        
        # Try multiple Quran audio CDNs
        urls_to_try = [
            f"https://cdn.islamic.network/quran/audio-surah/128/ar.alafasy/{surah_num}.mp3",
            f"https://cdn.islamic.network/quran/audio/128/ar.alafasy/{surah_num}.mp3",
            f"https://everyayah.com/data/Alafasy_128kbps/{surah_num:03d}.mp3",
            f"https://www.everyayah.com/data/Alafasy_128kbps/{surah_num:03d}.mp3",
        ]
        
        for url in urls_to_try:
            try:
                print(f"[QURAN] Trying {url}")
                r = requests.get(url, timeout=15)
                if r.status_code == 200 and len(r.content) > 10000:
                    mp3_data = r.content
                    print(f"[QURAN] Got MP3 {len(mp3_data)} bytes from {url}")
                    
                    # Convert MP3 to WAV 16kHz mono for ESP32
                    try:
                        from pydub import AudioSegment
                        mp3_io = io.BytesIO(mp3_data)
                        sound = AudioSegment.from_file(mp3_io, format="mp3")
                        # Limit to first 60 seconds for ESP32 memory
                        if len(sound) > 60000:
                            sound = sound[:60000]
                        sound = sound.set_frame_rate(16000).set_channels(1).set_sample_width(2)
                        wav_io = io.BytesIO()
                        sound.export(wav_io, format="wav")
                        wav_data = wav_io.getvalue()
                        print(f"[QURAN] Converted to WAV {len(wav_data)} bytes")
                        return wav_data
                    except Exception as conv_e:
                        print(f"[QURAN] Convert fail {conv_e}, returning MP3 as WAV fallback")
                        # Return as is - ESP32 can try to play?
                        # Better convert with simple method: still return wav
                        import wave
                        with io.BytesIO() as out:
                            with wave.open(out, "wb") as w:
                                w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
                                w.writeframes(b"\x00\x00" * 16000)
                            return out.getvalue()
            except Exception as e:
                print(f"[QURAN] Failed {url}: {e}")
                continue
        
        print("[QURAN] All CDNs failed, fallback to TTS")

    # Normal TTS path (Manglish/English)
    clean_text = re.sub(r'__QURAN_RECITE_\d+__', '', text).strip()
    if not clean_text:
        clean_text = "Bismillahirrahmanirrahim"
    
    print(f"[TTS] Clean text: {clean_text[:80]}")

    if SARVAM_API_KEY:
        try:
            url = "https://api.sarvam.ai/text-to-speech"
            headers = {"API-Subscription-Key": SARVAM_API_KEY}
            payload = {
                "inputs": [clean_text],
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
                audios = r.json().get("audios", [])
                if audios:
                    data = base64.b64decode(audios[0])
                    print(f"[TTS] Sarvam {len(data)}")
                    return data
        except Exception as e:
            print(f"[TTS] Sarvam {e}")

    try:
        from gtts import gTTS
        from pydub import AudioSegment
        mp3_io = io.BytesIO()
        try:
            tts = gTTS(text=clean_text, lang='ml', slow=False)
            tts.write_to_fp(mp3_io)
        except:
            tts = gTTS(text=clean_text, lang='en', tld='co.in', slow=False)
            tts.write_to_fp(mp3_io)
        mp3_io.seek(0)
        sound = AudioSegment.from_file(mp3_io, format="mp3")
        sound = sound.set_frame_rate(16000).set_channels(1).set_sample_width(2)
        wav_io = io.BytesIO()
        sound.export(wav_io, format="wav")
        wav_data = wav_io.getvalue()
        print(f"[TTS] gTTS {len(wav_data)}")
        return wav_data
    except Exception as e:
        print(f"[TTS] gTTS {e}")

    try:
        import edge_tts, asyncio
        from pydub import AudioSegment
        async def _run():
            tmp = "/tmp/edge.mp3"
            try:
                comm = edge_tts.Communicate(clean_text, "ml-IN-AnjanaNeural")
                await comm.save(tmp)
            except:
                comm = edge_tts.Communicate(clean_text, "en-IN-NeerjaNeural")
                await comm.save(tmp)
            snd = AudioSegment.from_file(tmp)
            snd = snd.set_frame_rate(16000).set_channels(1).set_sample_width(2)
            out = io.BytesIO()
            snd.export(out, format="wav")
            return out.getvalue()
        data = asyncio.run(_run())
        print(f"[TTS] edge {len(data)}")
        return data
    except Exception as e:
        print(f"[TTS] edge {e}")

    import wave
    with io.BytesIO() as out:
        with wave.open(out, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
            w.writeframes(b"\x00\x00" * 16000)
        return out.getvalue()
