import os
from groq import Groq
import google.generativeai as genai

# 2026 GROQ MODELS - Latest (Llama 4)
GROQ_MODELS_2026 = [
    "llama-3.3-70b-versatile",  # Still active on many accounts
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-3.1-8b-instant",  # Try again, may work after env fix
    "qwen/qwen3-32b",
    "deepseek-r1-distill-llama-70b",
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

def synthesize(text, mood="happy"):
    # 1. Try Groq
    reply = try_groq(text)
    if reply:
        return reply
    
    # 2. Try Gemini (you have key in env)
    reply = try_gemini(text)
    if reply:
        return reply
    
    # 3. Malayalam fallback - NOT English
    print("[ALL] Using Malayalam fallback")
    # Rotate fallback to avoid same replay
    import random
    fallbacks = [
        "Wa Alaikum Salam! Njan HYZIN aanu, enthu sahayam venam?",
        "Njan HYZIN aanu, Mashood Thennala undaakkiyathu! Enth parayan ullu?",
        "Enthokke undu? Njan HYZIN aanu, sahayikatte?",
        "Hello! Njan HYZIN aanu, entha cheyyendathu?",
    ]
    return random.choice(fallbacks)
