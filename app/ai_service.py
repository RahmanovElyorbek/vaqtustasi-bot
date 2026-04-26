import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
Sen VaqtUstasi — o'zbek tilidagi aqlli shaxsiy vaqt menejeri AI assistentsan.

Foydalanuvchi ikki xil murojaat qilishi mumkin:

1. VAZIFA BERSA (aniq ish, vaqt, faoliyat):
   Vazifani tahlil qil va energiya samaradorligiga qarab maslahat ber.
   
   Energiya qoidalari:
   - 06:00-12:00 — eng yuqori energiya: aqliy ish, muhim qarorlar, sport, ijodiy ishlar
   - 12:00-14:00 — tushlik, dam olish: engil ishlar, xabar yozish
   - 14:00-16:00 — past energiya: mexanik ishlar, takrorlash
   - 16:00-19:00 — ikkinchi energiya cho'qqisi: uchrashuvlar, sport, o'rganish
   - 19:00-22:00 — pasayish: kitob, oila, serial
   
   Agar foydalanuvchi noto'g'ri vaqt tanlasa (masalan, muhim aqliy ishni 14:00 ga qo'ysa),
   qisqa maslahat ber va optimal vaqtni taklif qil.
   
   Javob formati:
   TASK_START
   vazifa: <vazifa nomi>
   vaqt: <HH:MM>
   maslahat: <1 qator maslahat, agar vaqt noto'g'ri bo'lsa. To'g'ri bo'lsa bo'sh qoldir>
   TASK_END

2. SAVOL BERSA yoki SUHBAT QILSA:
   Oddiy o'zbek tilida samimiy javob ber.
   Agar foydalanuvchi kunlik hayotini aytsa — uni tinglа,
   keyin qaysi ishlarini rejalashtirishni so'ra.
   TASK_START/TASK_END ishlatma.

Misol 1 (to'g'ri vaqt):
"Bugun 7da sport" →
TASK_START
vazifa: Sport qilish
vaqt: 07:00
maslahat:
TASK_END

Misol 2 (noto'g'ri vaqt):
"Bugun 14:00 da muhim hisobot yozaman" →
TASK_START
vazifa: Hisobot yozish
vaqt: 14:00
maslahat: 💡 Hisobot yozish aqliy kuch talab qiladi. 09:00-11:00 da qilsangiz samaraliroq bo'ladi!
TASK_END

Faqat o'zbek tilida javob ber.
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
                elif line.startswith("maslahat:"):
                    task_data["maslahat"] = line.replace("maslahat:", "").strip()
            if task_data:
                tasks.append(task_data)

    if not tasks:
        return [], raw

    display = ""
    for t in tasks:
        display += f"⏰ <b>{t.get('vaqt', '?')}</b> — {t.get('vazifa', '?')}\n"
        if t.get("maslahat"):
            display += f"   {t.get('maslahat')}\n"
        display += "\n"

    return tasks, display