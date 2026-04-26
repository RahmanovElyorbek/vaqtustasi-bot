import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
Sen VaqtUstasi — o'zbek tilidagi aqlli shaxsiy vaqt menejeri AI assistentsan.

Foydalanuvchi senga kunlik vazifalarini aytadi. Sen:

1. Har bir vazifani tahlil qilasan
2. Optimal vaqtni belgilaysan (HH:MM formatida)
3. Qisqa va aniq reja tuzasan

Javob formati (faqat shu formatda, boshqa narsa yozma):
TASK_START
vazifa: <vazifa nomi>
vaqt: <HH:MM>
TASK_END

Bir nechta vazifa bo'lsa, har birini alohida TASK_START...TASK_END ichida yoz.

Misol:
TASK_START
vazifa: Sport qilish
vaqt: 07:00
TASK_END
TASK_START
vazifa: Ingliz tili
vaqt: 19:00
TASK_END

Faqat o'zbek tilida javob ber. Ortiqcha tushuntirma yozma.
"""


def generate_schedule(user_text: str) -> tuple[list, str]:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text}
        ],
        max_tokens=500,
        timeout=15
    )
    
    raw = response.choices[0].message.content
    
    # Vazifalarni parse qilish
    tasks = []
    blocks = raw.split("TASK_START")
    for block in blocks[1:]:
        if "TASK_END" in block:
            content = block.split("TASK_END")[0].strip()
            lines = content.strip().split("\n")
            task_data = {}
            for line in lines:
                if line.startswith("vazifa:"):
                    task_data["vazifa"] = line.replace("vazifa:", "").strip()
                elif line.startswith("vaqt:"):
                    task_data["vaqt"] = line.replace("vaqt:", "").strip()
            if task_data:
                tasks.append(task_data)
    
    # Foydalanuvchiga ko'rsatiladigan matn
    display = ""
    for t in tasks:
        display += f"⏰ <b>{t.get('vaqt', '?')}</b> — {t.get('vazifa', '?')}\n"
    
    return tasks, display