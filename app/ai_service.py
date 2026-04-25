import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are a smart personal time management AI assistant for Uzbek users.

Your job:
- Understand user's task written in Uzbek or Russian
- Assign realistic time slots
- Create a clear daily schedule
- Keep it concise and practical

Output format (in Uzbek):
📋 Vazifa: ...
⏰ Tavsiya etilgan vaqt: ...
📅 Reja: ...
"""

def generate_schedule(user_text: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text}
        ],
        max_tokens=500,
        timeout=15
    )
    return response.choices[0].message.content