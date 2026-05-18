import os
import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from openai import OpenAI

logger = logging.getLogger(__name__)

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
    
    return f"""Sen — VaqtUstasi, o'zbek tilida ishlovchi shaxsiy vaqt menejmenti AI yordamchisi. Mijozing — Toshkentdagi supermarket bosh menejeri.

BUGUN: {today_str} ({weekday}), HOZIR: {current_time}

MIJOZ TARTIBI:
• 07:00–18:30 — ish vaqti (supermarketda)
• 13:00–13:20 — tushlik (ish qo'yma)
• Namoz vaqtlari — bo'sh bo'lishi kerak (Bomdod, Peshin, Asr, Shom, Xufton)
• 18:30 dan keyin — uy vaqti (ish masalalarini ertaga qoldir)

JAVOB QOIDALARI:
1. FAQAT o'zbek tilida (lotin yozuvi). Turk/ozarbayjon tiliga aralashtirma.
2. Har javob 2-4 jumladan oshmasin. Qisqa va aniq.
3. ANIQ vaqt va ANIQ harakat ayt — "rejalashtiring" emas, "soat 10:00 da boshlang, 30 daqiqa" deb ayt.
4. "Hurmatli mijoz", "Hurmatli menejer" deb murojaat QILMA. Oddiy gaplash.
5. Har javob oxiriga "Yordam berishga tayyorman", "Marhamat", "Katta rahmat" kabi jumlalar QO'SHMA.
6. "Raqamli", "operativ", "dasturiy ta'minot" kabi bo'sh so'zlardan foydalanma.
7. Agar so'rov noaniq bo'lsa — aniqlashtiruvchi savol ber.

JAVOB FORMATI:
Sen har doim JSON formatda javob qaytar. Hech qachon JSON tashqarisida matn yozma.

{{
  "javob": "Foydalanuvchiga ko'rinadigan matn (2-4 jumla)",
  "vazifalar": [
    {{
      "nomi": "vazifa nomi",
      "sana_vaqt": "YYYY-MM-DD HH:MM",
      "izoh": "qisqa strategik maslahat"
    }}
  ]
}}

Agar vazifa qo'shilmasa, "vazifalar" bo'sh ro'yxat bo'ladi: []

MISOLLAR:

Foydalanuvchi: "Ertaga 10:00 da firma bilan uchrashuvim bor"
Sen:
{{
  "javob": "Yaxshi, ertaga 10:00 da uchrashuvni qo'shdim. Tayyorgarlik uchun bugun 21:00–21:30 oralig'ida 30 daqiqa ajrating — material o'qib, savollar ro'yxatini tuzing.",
  "vazifalar": [
    {{"nomi": "Firma bilan uchrashuv", "sana_vaqt": "2026-05-19 10:00", "izoh": "Ish vaqti ichida"}},
    {{"nomi": "Uchrashuvga tayyorgarlik", "sana_vaqt": "2026-05-18 21:00", "izoh": "Uy vaqti, 30 daqiqa"}}
  ]
}}

Foydalanuvchi: "Vaqtim yetmayapti"
Sen:
{{
  "javob": "Bugun nechta vazifa bor va ulardan eng muhimi qaysi? Aniq aytsangiz, soat bo'yicha reja tuzaman.",
  "vazifalar": []
}}

Foydalanuvchi: "Sport bilan qachon shug'ullanay?"
Sen:
{{
  "javob": "Ish 18:30 da tugaydi. 19:00–20:00 oralig'ida 45 daqiqa sport uchun ajrating — bu Xufton namozigacha tugaydi.",
  "vazifalar": [
    {{"nomi": "Sport", "sana_vaqt": "2026-05-18 19:00", "izoh": "Ish va Xufton orasida"}}
  ]
}}
"""


def generate_schedule(user_text: str, conversation_history: list = None) -> tuple[list, str]:
    """
    user_text: yangi foydalanuvchi xabari
    conversation_history: [{"role": "user/assistant", "content": "..."}]
    """
    if conversation_history is None:
        conversation_history = []
    
    # Oxirgi 10 ta xabarni olish
    recent = conversation_history[-10:]
    
    messages = [{"role": "system", "content": get_system_prompt()}]
    messages.extend(recent)
    messages.append({"role": "user", "content": user_text})
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=600,
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        
        raw = response.choices[0].message.content
        data = json.loads(raw)
        
        tasks = []
        for v in data.get("vazifalar", []):
            try:
                dt = datetime.strptime(v["sana_vaqt"], "%Y-%m-%d %H:%M").replace(tzinfo=UZ_TZ)
                tasks.append({
                    "vazifa": v["nomi"],
                    "sana_vaqt": dt,
                    "maslahat": v.get("izoh", "")
                })
            except (KeyError, ValueError) as e:
                logger.warning(f"Vazifa parse xatosi: {e}, data: {v}")
                continue
        
        javob = data.get("javob", "Kechirasiz, javob bera olmadim.")
        return tasks, javob
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse xato: {e}, raw: {raw if 'raw' in locals() else 'N/A'}")
        return [], "Kechirasiz, javob formatida xato. Qayta urinib ko'ring."
    except Exception as e:
        logger.error(f"OpenAI API xato: {e}", exc_info=True)
        return [], "Kechirasiz, texnik muammo. Birozdan keyin urinib ko'ring."


def transcribe_audio(audio_file_path: str) -> str:
    """
    Audio faylni transkripsiya qiladi.
    """
    try:
        # Fayl hajmini tekshirish
        file_size = os.path.getsize(audio_file_path)
        logger.info(f"Audio fayl hajmi: {file_size} bayt, yo'l: {audio_file_path}")
        
        if file_size < 1000:  # 1KB dan kichik — juda qisqa
            logger.warning(f"Audio juda kichik: {file_size} bayt")
            return ""
        
        with open(audio_file_path, "rb") as f:
            # AVVAL language parametrisiz sinab ko'ramiz
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                prompt="Toshkent supermarket menejer vazifa uchrashuv namoz tushlik"
            )
        
        text = transcript.text.strip()
        logger.info(f"Whisper transkripsiya natijasi: '{text}' (uzunlik: {len(text)})")
        
        if not text:
            logger.warning("Whisper bo'sh matn qaytardi")
        
        return text
        
    except Exception as e:
        logger.error(f"Whisper xato: {type(e).__name__}: {e}", exc_info=True)
        return ""
