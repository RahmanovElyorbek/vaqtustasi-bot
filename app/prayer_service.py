import os
import logging
import requests
from datetime import datetime, date
from zoneinfo import ZoneInfo
from app.database import (
    save_prayer_times, get_users_with_location, get_prayer_times
)

logger = logging.getLogger(__name__)
UZ_TZ = ZoneInfo("Asia/Tashkent")


def fetch_prayer_times(latitude: float, longitude: float, target_date: date = None):
    """
    Aladhan API'dan namoz vaqtlarini olish.
    Method 2 = Islamic Society of North America.
    School 1 = Hanafi (O'zbekiston uchun).
    """
    if target_date is None:
        target_date = datetime.now(UZ_TZ).date()
    
    date_str = target_date.strftime("%d-%m-%Y")
    url = f"https://api.aladhan.com/v1/timings/{date_str}"
    
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "method": 2,
        "school": 1
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        timings = data["data"]["timings"]
        
        # "13:00 (+05)" -> "13:00"
        def clean_time(t):
            return t.split(" ")[0]
        
        return {
            "fajr": clean_time(timings["Fajr"]),
            "dhuhr": clean_time(timings["Dhuhr"]),
            "asr": clean_time(timings["Asr"]),
            "maghrib": clean_time(timings["Maghrib"]),
            "isha": clean_time(timings["Isha"])
        }
    except Exception as e:
        logger.error(f"Aladhan API xato: {e}", exc_info=True)
        return None


def update_all_users_prayer_times():
    """
    Har kuni 00:01 da chaqiriladi.
    Barcha foydalanuvchilar uchun bugungi namoz vaqtlarini yangilaydi.
    """
    users = get_users_with_location()
    logger.info(f"Namoz vaqtlari yangilanyapti: {len(users)} foydalanuvchi")
    
    today = datetime.now(UZ_TZ).date()
    success = 0
    
    for user in users:
        times = fetch_prayer_times(user["latitude"], user["longitude"], today)
        if times:
            save_prayer_times(user["user_id"], today, times)
            success += 1
            logger.info(f"User {user['user_id']} uchun namoz vaqtlari saqlandi")
        else:
            logger.warning(f"User {user['user_id']} uchun API xato")
    
    logger.info(f"Namoz vaqtlari yangilandi: {success}/{len(users)}")


def get_today_prayer_times_text(user_id: int) -> str:
    """Bugungi namoz vaqtlarini chiroyli matn qilib qaytaradi"""
    today = datetime.now(UZ_TZ).date()
    times = get_prayer_times(user_id, today)
    
    if not times:
        return "❌ Namoz vaqtlari hali sozlanmagan. Lokatsiyangizni yuboring."
    
    return (
        f"🕌 <b>Bugungi namoz vaqtlari</b>\n"
        f"📅 {today.strftime('%d-%m-%Y')}\n\n"
        f"🌅 Bomdod: <b>{times['fajr'].strftime('%H:%M')}</b>\n"
        f"☀️ Peshin: <b>{times['dhuhr'].strftime('%H:%M')}</b>\n"
        f"🌤 Asr: <b>{times['asr'].strftime('%H:%M')}</b>\n"
        f"🌆 Shom: <b>{times['maghrib'].strftime('%H:%M')}</b>\n"
        f"🌙 Xufton: <b>{times['isha'].strftime('%H:%M')}</b>"
    )


def ensure_today_prayer_times(user_id: int, latitude: float, longitude: float):
    """
    Agar bugungi namoz vaqtlari yo'q bo'lsa, darhol oladi va saqlaydi.
    Foydalanuvchi yangi lokatsiya berganida ishlatiladi.
    """
    today = datetime.now(UZ_TZ).date()
    existing = get_prayer_times(user_id, today)
    
    if not existing:
        times = fetch_prayer_times(latitude, longitude, today)
        if times:
            save_prayer_times(user_id, today, times)
            return True
        return False
    return True