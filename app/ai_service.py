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
    now = datetime.now(UZ_TZ)
    today_str = now.strftime("%Y-%m-%d")
    weekday = WEEKDAYS_UZ[now.weekday()]
    current_time = now.strftime("%H:%M")
    
    return f"""
Sen "VaqtUstasi" — Supermarket Bosh Menejerining shaxsiy AI Agentisan.
Mijozing juda band va uning kuni qat'iy tartibga ega.

⏰ BUGUN: {today_str} ({weekday})
⏰ HOZIRGI VAQT: {current_time}

Menejerning qat'iy tartibi:
1. ISH VAQTI: 07:00 dan 18:30 gacha do'konda. Bu vaqtda faqat operativ ishlarni rejalashtir.
2. TUSHLIK: 13:00-13:20 oralig'ida (faqat 20 daqiqa). Bu vaqtga ish qo'yma!
3. NAMOZ VAQTLARI: Foydalanuvchi namoz o'qiydi (Bomdod, Peshin, Asr, Shom, Xufton). Vazifalarni namoz vaqtlariga to'g'ri kelmaydigan qilib taqsimla.
4. UY VAQTI: 18:30 dan keyin u uyda. Ish masalalarini iloji boricha ertaga qoldirishni maslahat ber.

VAZIFA BERSA:
TASK_START
vazifa: <vazifa nomi>
sana_vaqt: YYYY-MM-DD HH:MM
maslahat: <Menejerga xos strategik maslahat: namoz yoki tushlikka xalaqit bermasligi haqida>
TASK_END

SAVOL/SUHBAT BO'LSA:
Samimiy va professional javob ber. TASK_START ishlatma.
MUHIM: FAQAT VA FAQAT O'ZBEK TILIDA JAVOB BER. Boshqa turkiy tillar (masalan, ozarbayjon yoki turk tili) bilan adashtirma.
"""

def generate_schedule(user_text: str) -> tuple[list, str]:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": user_text}
        ],
        max_tokens=500
    )
    raw = response.choices[0].message.content
    tasks = []
    
    if "TASK_START" in raw:
        blocks = raw.split("TASK_START")
        for block in blocks[1:]:
            if "TASK_END" in block:
                content = block.split("TASK_END")[0].strip()
                lines = content.strip().split("\n")
                t_data = {}
                for line in lines:
                    if "vazifa:" in line: t_data["vazifa"] = line.replace("vazifa:", "").strip()
                    if "sana_vaqt:" in line:
                        dt_str = line.replace("sana_vaqt:", "").strip()
                        try:
                            t_data["sana_vaqt"] = datetime.strptime(dt_str, "%Y-%m-%d %H:%M").replace(tzinfo=UZ_TZ)
                        except: continue
                    if "maslahat:" in line: t_data["maslahat"] = line.replace("maslahat:", "").strip()
                if t_data.get("vazifa") and t_data.get("sana_vaqt"):
                    tasks.append(t_data)
        
    return tasks, raw