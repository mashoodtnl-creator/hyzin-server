import os
from groq import Groq

# GROQ MODEL - FIXED 2026 - llama-3.1-8b-instant DEPRECATED!
# Use models that actually exist on GroqCloud
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-8b-8192")  # This exists 100%

# Fallback models if first fails
FALLBACK_MODELS = [
    "llama3-8b-8192",
    "llama-3.3-70b-versatile",
    "llama-3.1-70b-versatile",
    "gemma2-9b-it",
    "mixtral-8x7b-32768"
]

def get_groq_client():
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise ValueError("GROQ_API_KEY missing")
    return Groq(api_key=key)

# MALAYALAM SYSTEM PROMPT - FINAL V1
MALAYALAM_PROMPT = """You are HYZIN, created by Mashood Thennala.

CRITICAL RULES:
1. ALWAYS reply in Malayalam - Manglish (Malayalam in English letters) is PREFERRED.
   Example: "Enthokke undu?", "Njan HYZIN aanu, entha sahayam venam?"
2. If user says Salam/Assalamu Alaikum, reply: "Wa Alaikum Salam! Enthokke undu? Njan HYZIN aanu!"
3. Keep answer SHORT - 1 or 2 lines only, max 20 words.
4. Never repeat same answer. Be friendly.
5. If user speaks English, still reply in Manglish Malayalam.

Examples:
User: Nee aara?
You: Njan HYZIN aanu, Mashood Thennala undaakkiyathu! Enth sahayam venam?

User: Assalamu Alaikum
You: Wa Alaikum Salam! Enthokke undu?

User: What is your name?
You: Ente peru HYZIN aanu!
"""

def synthesize(text, mood="happy"):
    client = get_groq_client()
    
    # Try main model + fallbacks
    for model_name in [GROQ_MODEL] + FALLBACK_MODELS:
        try:
            print(f"[GROQ] Trying model: {model_name}")
            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": MALAYALAM_PROMPT},
                    {"role": "user", "content": text if text else "Nee aara?"}
                ],
                model=model_name,
                temperature=0.7,
                max_tokens=80,
            )
            reply = chat_completion.choices[0].message.content.strip()
            if reply:
                print(f"[GROQ] SUCCESS with {model_name}: {reply[:100]}")
                return reply
        except Exception as e:
            print(f"[GROQ] Model {model_name} failed: {e}")
            continue
    
    # All failed - Malayalam fallback, NOT English
    print("[GROQ] All models failed, using Malayalam fallback")
    return "Wa Alaikum Salam! Njan HYZIN aanu, enthu sahayam venam?"
