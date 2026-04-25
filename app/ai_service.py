from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are a smart personal time management AI.

Your job:
- Understand user's task
- Assign realistic time
- Keep it short

Output:
Task: ...
Scheduled Time: ...
"""

def generate_schedule(user_text):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text}
            ],
            timeout=8
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"AI ERROR: {type(e).__name__}: {e}")
        raise