import os
from datetime import datetime
from zoneinfo import ZoneInfo
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
UZ_TZ = ZoneInfo("Asia/Tashkent")

WEEKDAYS_UZ = {
    0: "Dushanba", 1: "Seshanba", 2: "Chorshanba",
    3: "Payshanba", 4: "Juma", 5: "Shanba", 6: "Yakshanba"
}


def get_system_prompt():
    """Har safar yangi sana bilan prompt yaratamiz"""
    now = datetime.now(UZ_TZ)
    today_str = now.strftime("%Y-%m-%d")
    weekday = WEEKDAYS_UZ[now.weekday()]
    current_time = now.strftime("%H:%M")
    
    return f"""
Sen VaqtUstasi — o'zbek tilidagi aqlli shaxsiy vaqt menejeri AI assistentsan.

⏰ HOZIRGI SANA: {today_str} ({weekday})
⏰ HOZIRGI VAQT: {current_time}

Foydalanuvchi ikki xil murojaat qilishi mumkin:

1. VAZIFA BERSA (aniq ish, vaqt, faoliyat):
   Vazifani tahlil qil va energiya samaradorligiga qarab maslahat ber.
   
   MUHIM: Foydalanuvchi "ertaga", "dushanba", "3 kundan keyin" kabi so'zlarni ishlatsa,
   sen ularni HOZIRGI SANAga qarab to'liq sanaga aylantirib ber (YYYY-MM-DD HH:MM).
   
   Misollar (bugun {today_str} bo'lsa):
   - "Bugun 14da uchrashuv" → bugungi sana 14:00
   - "Ertaga 9da sport" → ertangi sana 09:00
   - "Juma kuni 16da" → keyingi juma kuni 16:00
   
   Energiya qoidalari (biznesmenlar uchun):
   - 06:00-09:00 — eng yuqori energiya: strategik ishlar, muhim qarorlar
   - 09:00-12:00 — uchrashuvlar, qo'ng'iroqlar, hisobotlar
   - 12:00-14:00 — tushlik, dam olish
   - 14:00-16:00 — operativ ishlar, xat-xabarlar
   - 16:00-19:00 — ikkinchi cho'qqi: uchrashuvlar, sport
   - 19:00+ — oila, dam olish (ish vazifalari tavsiya etilmaydi)
   
   Agar foydalanuvchi noto'g'ri vaqt tanlasa, qisqa maslahat ber.
   
   Javob formati:
   TASK_START
   vazifa: <vazifa nomi>
   sana_vaqt: <YYYY-MM-DD HH:MM>
   maslahat: <1 qator maslahat, kerak bo'lsa. Bo'lmasa bo'sh qoldir>
   TASK_END

2. SAVOL/SUHBAT BO'LSA:
   Oddiy o'zbek tilida samimiy javob ber.
   TASK_START/TASK_END ishlatma.

Misol 1:
"Ertaga 7da sport" →
TASK_START
vazifa: Sport qilish
sana_vaqt: <ertangi sana> 07:00
maslahat:
TASK_END

Misol 2:
"Bugun 14:00 da muhim hisobot yozaman" →
TASK_START
vazifa: Hisobot yozish
sana_vaqt: {today_str} 14:00
maslahat: 💡 Hisobot yozish aqliy kuch talab qiladi. 09:00-11:00 da samaraliroq bo'ladi!
TASK_END

Faqat o'zbek tilida javob ber.
"""


def generate_schedule(user_text: str) -> tuple[list, str]:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": get_system_prompt()},
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
                elif line.startswith("sana_vaqt:"):
                    datetime_str = line.replace("sana_vaqt:", "").strip()
                    # "2026-04-27 14:00" formatini datetime ga aylantirish
                    try:
                        dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
                        # Uzbekiston timezone bilan birlashtirish
                        dt = dt.replace(tzinfo=UZ_TZ)
                        task_data["sana_vaqt"] = dt
                    except ValueError as e:
                        print(f"DATE PARSE ERROR: {e}, raw: {datetime_str}")
                        continue
                elif line.startswith("maslahat:"):
                    task_data["maslahat"] = line.replace("maslahat:", "").strip()
            
            if task_data.get("vazifa") and task_data.get("sana_vaqt"):
                tasks.append(task_data)

    if not tasks:
        return [], raw

    display = ""
    for t in tasks:
        dt = t["sana_vaqt"]
        weekday = WEEKDAYS_UZ[dt.weekday()]
        display += f"⏰ <b>{dt.strftime('%d-%B, %H:%M')} ({weekday})</b>\n"
        display += f"   📌 {t['vazifa']}\n"
        if t.get("maslahat"):
            display += f"   {t['maslahat']}\n"
        display += "\n"

    return tasks, display