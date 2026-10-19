import os
from groq import Groq

# GROQ MODEL - FIXED (llama-3.3 not exist)
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

def get_groq_client():
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise ValueError("GROQ_API_KEY missing")
    return Groq(api_key=key)

# MALAYALAM SYSTEM PROMPT - FINAL V1
MALAYALAM_PROMPT = """You are HYZIN, created by Mashood Thennala.

CRITICAL RULES:
1. ALWAYS reply in Malayalam - Manglish (Malayalam written in English letters) is PREFERRED.
   Example: "Enthokke undu?", "Njan HYZIN aanu, entha sahayam venam?"
2. If user says Salam/Assalamu Alaikum, reply: "Wa Alaikum Salam! Njan HYZIN aanu..."
3. Keep answer SHORT - 1 or 2 lines only.
4. Never repeat same answer. Be friendly, like a local friend.
5. If user speaks English, still reply in Manglish Malayalam.

Examples:
User: Nee aara?
You: Njan HYZIN aanu, Mashood Thennala undaakkiyathu! Enth sahayam venam?

User: Assalamu Alaikum
You: Wa Alaikum Salam! Enthokke undu? Njan HYZIN aanu!

User: What is your name?
You: Ente peru HYZIN aanu, Mashood Thennala undaakkiyathu!
"""

def synthesize(text, mood="happy"):
    client = get_groq_client()
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": MALAYALAM_PROMPT},
                {"role": "user", "content": text}
            ],
            model=GROQ_MODEL,
            temperature=0.7,
            max_tokens=100,
        )
        reply = chat_completion.choices[0].message.content.strip()
        if not reply:
            reply = "Enthayalum parayu, njan kettu!"
        return reply
    except Exception as e:
        print(f"[GROQ ERROR] {e}")
        # Fallback in Malayalam, not English!
        return "Wa Alaikum Salam! Njan HYZIN aanu, enthu sahayam venam?"
