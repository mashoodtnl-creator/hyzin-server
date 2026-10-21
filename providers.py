import os, io, base64, re, requests

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")

SURAH_MAP = {
    "fatiha": 1, "fathih": 1, "baqarah": 2, "yaseen": 36, "yasin": 36,
    "rahman": 55, "mulk": 67, "kahf": 18, "ikhlas": 112, "falaq": 113, "nas": 114,
    "kawthar": 108, "asr": 103, "qadr": 97, "fil": 105, "quraish": 106,
}

def _detect_surah(text: str) -> int:
    low = text.lower()
    for name, num in SURAH_MAP.items():
        if name in low:
            return num
    qwords = ["quran othu", "surah", "othu", "recite", "tilawat", "qirat", "ayat odu"]
    if any(k in low for k in qwords):
        return 1
    return 0

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
        return "Assalamu Alaikum"
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        result = client.audio.transcriptions.create(
            file=("audio.wav", wav_data),
            model="whisper-large-v3",
            language="ml",
            response_format="text",
            prompt="Malayalam Manglish Quran Surah Fatiha Ikhlas Yaseen Iqbal"
        )
        text = result.strip() if isinstance(result, str) else getattr(result, 'text', str(result)).strip()
        print(f"[STT] {text}")
        return text
    except Exception as e:
        print(f"[STT] Error {e}")
        return "Assalamu Alaikum"

def answer(question: str) -> str:
    question = (question or "").strip()
    print(f"[LLM] Q: {question}")
    if not question or question == "[NO_SPEECH]":
        return "Assalamu Alaikum, enth sahayam venam?"

    ql = question.lower()

    # === NO AUTO REPEAT FIX ===
    # Only give Salam greeting if user actually said Salam
    is_salam = any(w in ql for w in ["assalam", "salam", "alsalam"])
    
    # Quran recitation detection
    surah_num = _detect_surah(question)
    if surah_num > 0:
        names = {1:"Fatiha",2:"Baqarah",18:"Kahf",36:"Yaseen",55:"Rahman",67:"Mulk",108:"Kawthar",112:"Ikhlas",113:"Falaq",114:"Nas"}
        sname = names.get(surah_num, f"Surah {surah_num}")
        return f"__QURAN_RECITE_{surah_num}__ {sname} othunnu"

    if not GROQ_API_KEY:
        if is_salam:
            return "Wa Alaikum Salam! Njan HYZIN aanu, enth padikkanam?"
        # Dynamic fallback - NOT same repeat
        return f"Njan kettathu: {question}. Ithine kurichu parayamo?"

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        system = f"""You are HYZIN V1 by Mashood Thennala, Quran companion.
RULES - VERY IMPORTANT:
- User said: '{question}'
- Reply ONLY to what user asked. NO auto repeat same greeting.
- If user says Salam -> reply Wa Alaikum Salam warmly
- If user says name like Iqbal, Subhishriya, etc -> greet them by name, ask what they want to learn
- If user asks Quran/Surah -> reply __QURAN_RECITE_N__ format
  Example: Surah Ikhlas -> __QURAN_RECITE_112__ Surah Ikhlas
- Keep answer SHORT 1 sentence in Manglish (Malayalam in English letters)
- Be dynamic, never repeat "Wa Alaikum Salam! Njan HYZIN aanu, enth padikkanam?" for every question
- User's question: {question}"""

        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role":"system","content":system},
                {"role":"user","content":question}
            ],
            max_tokens=100,
            temperature=0.9
        )
        ans = resp.choices[0].message.content.strip()
        # Prevent same greeting loop - if answer is same generic greeting but question is not salam, make it dynamic
        if ans == "Wa Alaikum Salam! Njan HYZIN aanu, enth padikkanam?" and not is_salam:
            ans = f"Njan kettathu: {question}. Ithine kurichu enthariyanam?"
        print(f"[LLM] A: {ans}")
        return ans[:250]
    except Exception as e:
        print(f"[LLM] Fail {e}")
        if is_salam:
            return "Wa Alaikum Salam! Njan HYZIN aanu, enth padikkanam?"
        return f"Njan kettathu {question}, enth sahayam venam?"

def language_for(text: str) -> str:
    return "ml-IN"

def synthesize(text: str, lang: str = "ml") -> bytes:
    print(f"[SYNTH] {text[:120]}")
    match = re.search(r'__QURAN_RECITE_(\d+)__', text)
    if match:
        surah_num = int(match.group(1))
        print(f"[QURAN] Surah {surah_num} recitation")
        urls = [
            f"https://cdn.islamic.network/quran/audio-surah/128/ar.alafasy/{surah_num}.mp3",
            f"https://everyayah.com/data/Alafasy_128kbps/{surah_num:03d}.mp3",
        ]
        for url in urls:
            try:
                r = requests.get(url, timeout=15)
                if r.status_code == 200 and len(r.content) > 10000:
                    mp3_data = r.content
                    from pydub import AudioSegment
                    mp3_io = io.BytesIO(mp3_data)
                    sound = AudioSegment.from_file(mp3_io, format="mp3")
                    if len(sound) > 60000:
                        sound = sound[:60000]
                    sound = sound.set_frame_rate(16000).set_channels(1).set_sample_width(2)
                    wav_io = io.BytesIO()
                    sound.export(wav_io, format="wav")
                    wav_data = wav_io.getvalue()
                    print(f"[QURAN] WAV {len(wav_data)}")
                    return wav_data
            except Exception as e:
                print(f"[QURAN] fail {e}")
                continue

    clean_text = re.sub(r'__QURAN_RECITE_\d+__', '', text).strip()
    if not clean_text:
        clean_text = "Assalamu Alaikum"

    if SARVAM_API_KEY:
        try:
            url = "https://api.sarvam.ai/text-to-speech"
            headers = {"API-Subscription-Key": SARVAM_API_KEY}
            payload = {
                "inputs": [clean_text],
                "target_language_code": "ml-IN",
                "speaker": "anushka",
                "pace": 0.95,
                "speech_sample_rate": 16000,
                "model": "bulbul:v1"
            }
            r = requests.post(url, json=payload, headers=headers, timeout=20)
            if r.status_code == 200:
                audios = r.json().get("audios", [])
                if audios:
                    return base64.b64decode(audios[0])
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
        return wav_io.getvalue()
    except Exception as e:
        print(f"[TTS] gTTS {e}")

    import wave
    with io.BytesIO() as out:
        with wave.open(out, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
            w.writeframes(b"\x00\x00" * 16000)
        return out.getvalue()
