import os
import uuid
import logging
import telebot
from flask import Flask, request
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from zoneinfo import ZoneInfo

from app.ai_service import generate_schedule, transcribe_audio
from app.database import (
    init_db, save_user, save_task, get_pending_tasks, 
    mark_reminded, mark_done, mark_task_status,
    save_message, get_recent_messages, cleanup_old_messages,
    save_user_location, get_user_location,
    get_upcoming_prayer_reminders, mark_prayer_reminded
)
from app.prayer_service import (
    update_all_users_prayer_times, get_today_prayer_times_text,
    ensure_today_prayer_times
)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
UZ_TZ = ZoneInfo("Asia/Tashkent")

# Audio fayllar uchun papka
AUDIO_DIR = "/tmp/voice_files"
os.makedirs(AUDIO_DIR, exist_ok=True)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=False)
app = Flask(__name__)

init_db()


# --- Vazifa eslatmalari
def check_reminders():
    try:
        tasks = get_pending_tasks()
        for task in tasks:
            try:
                bot.send_message(
                    task["user_id"],
                    f"⏰ <b>Vaqt bo'ldi!</b>\n\n📌 {task['task_text']}\n\nBajardingizmi?",
                    reply_markup=done_keyboard(task["id"])
                )
                mark_reminded(task["id"])
            except Exception as e:
                logger.error(f"Eslatma yuborishda xato (task {task['id']}): {e}")
    except Exception as e:
        logger.error(f"check_reminders umumiy xato: {e}", exc_info=True)


# --- Namoz eslatmalari
def check_prayer_reminders():
    try:
        reminders = get_upcoming_prayer_reminders()
        for r in reminders:
            try:
                time_str = r["time"].strftime("%H:%M")
                bot.send_message(
                    r["user_id"],
                    f"🕌 <b>{r['prayer_name_uz']} vaqti yaqinlashmoqda</b>\n\n"
                    f"⏰ Vaqt: <b>{time_str}</b>\n"
                    f"📿 Tayyorlanish uchun 15 daqiqa qoldi"
                )
                mark_prayer_reminded(r["id"], r["prayer"])
            except Exception as e:
                logger.error(f"Namoz eslatma xato (user {r['user_id']}): {e}")
    except Exception as e:
        logger.error(f"check_prayer_reminders xato: {e}", exc_info=True)


def done_keyboard(task_id):
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(
        telebot.types.InlineKeyboardButton("✅ Bajardim", callback_data=f"done_{task_id}"),
        telebot.types.InlineKeyboardButton("❌ Yo'q", callback_data=f"skip_{task_id}")
    )
    return keyboard


# --- Scheduler
scheduler = BackgroundScheduler(timezone=UZ_TZ)
scheduler.add_job(check_reminders, "interval", minutes=1, id="task_reminders")
scheduler.add_job(check_prayer_reminders, "interval", minutes=1, id="prayer_reminders")
scheduler.add_job(
    update_all_users_prayer_times, 
    "cron", 
    hour=0, 
    minute=1,
    id="daily_prayer_update"
)
scheduler.start()


# === BUYRUQLAR ===

@bot.message_handler(commands=['start'])
def handle_start(message):
    save_user(message.from_user.id, message.from_user.first_name)
    
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(telebot.types.KeyboardButton("📍 Lokatsiyani yuborish", request_location=True))
    
    bot.send_message(
        message.chat.id,
        f"Assalomu alaykum, {message.from_user.first_name}! 👋\n\n"
        f"Men <b>VaqtUstasi</b> — sizning shaxsiy vaqt menejmenti yordamchingizman.\n\n"
        f"🎯 Men nima qila olaman:\n"
        f"• Vazifalaringizni rejaga kiritaman\n"
        f"• Vaqti yetganda eslatib turaman\n"
        f"• Namoz vaqtlariga to'g'ri kelmaydigan qilib taqsimlayman\n"
        f"• Audio xabarlarni tushunaman\n\n"
        f"📍 Avval lokatsiyangizni yuboring — namoz vaqtlarini aniq belgilash uchun.",
        reply_markup=keyboard
    )


@bot.message_handler(commands=['namoz'])
def handle_namoz(message):
    text = get_today_prayer_times_text(message.from_user.id)
    bot.send_message(message.chat.id, text)


@bot.message_handler(commands=['help'])
def handle_help(message):
    bot.send_message(
        message.chat.id,
        "🤖 <b>VaqtUstasi yordam</b>\n\n"
        "📝 <b>Buyruqlar:</b>\n"
        "/start — Botni qayta ishga tushirish\n"
        "/namoz — Bugungi namoz vaqtlari\n"
        "/help — Yordam\n\n"
        "💬 <b>Qanday ishlatish:</b>\n"
        "• Matn yoki audio yuboring\n"
        "• Misol: \"Ertaga 10:00 da uchrashuv\"\n"
        "• Bot avtomatik vazifani qo'shadi va vaqti yetganda eslatadi"
    )


# === LOKATSIYA ===

@bot.message_handler(content_types=['location'])
def handle_location(message):
    try:
        user_id = message.from_user.id
        lat = message.location.latitude
        lon = message.location.longitude
        
        save_user(user_id, message.from_user.first_name)
        save_user_location(user_id, lat, lon)
        
        wait_msg = bot.send_message(message.chat.id, "🕌 <i>Namoz vaqtlari olinmoqda...</i>")
        success = ensure_today_prayer_times(user_id, lat, lon)
        
        if success:
            prayer_text = get_today_prayer_times_text(user_id)
            bot.edit_message_text(
                f"✅ <b>Lokatsiya saqlandi!</b>\n\n{prayer_text}\n\n"
                f"💡 Endi men sizga vazifalarni namoz vaqtlariga to'g'ri kelmaydigan qilib taqsimlayman.",
                chat_id=wait_msg.chat.id,
                message_id=wait_msg.message_id
            )
        else:
            bot.edit_message_text(
                "✅ Lokatsiya saqlandi, lekin namoz vaqtlarini olishda muammo. Keyinroq /namoz ni sinab ko'ring.",
                chat_id=wait_msg.chat.id,
                message_id=wait_msg.message_id
            )
    except Exception as e:
        logger.error(f"Location handler xato: {e}", exc_info=True)
        bot.send_message(message.chat.id, "❌ Lokatsiyani saqlashda xato.")


# === CALLBACK (Bajardim/Yo'q) ===

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        action, task_id = call.data.split("_", 1)
        task_id = int(task_id)
        
        if action == "done":
            mark_task_status(task_id, "done")
            bot.answer_callback_query(call.id, "✅ Ajoyib!")
            bot.delete_message(call.message.chat.id, call.message.message_id)
            
        elif action == "skip":
            mark_task_status(task_id, "skipped")
            bot.answer_callback_query(call.id, "Mayli, keyingi safar")
            bot.delete_message(call.message.chat.id, call.message.message_id)
            
    except Exception as e:
        logger.error(f"Callback xato: {e}", exc_info=True)
        try:
            bot.answer_callback_query(call.id, "❌ Xatolik")
        except:
            pass


# --- Ovozli xabarlar
@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    wait_msg = bot.send_message(message.chat.id, "🎤 <i>Eshityapman...</i>")
    
    audio_path = os.path.join(AUDIO_DIR, f"{message.from_user.id}_{uuid.uuid4().hex}.ogg")
    
    try:
        file_info = bot.get_file(message.voice.file_id)
        downloaded = bot.download_file(file_info.file_path)
        
        with open(audio_path, "wb") as f:
            f.write(downloaded)
        
        text = transcribe_audio(audio_path)
        
        if not text:
            bot.edit_message_text(
                "❌ Audio aniqlanmadi. Iltimos, qaytadan urinib ko'ring yoki matn yozing.",
                chat_id=wait_msg.chat.id, message_id=wait_msg.message_id
            )
            return
        
        bot.delete_message(message.chat.id, wait_msg.message_id)
        bot.send_message(message.chat.id, f"🎤 <i>Sizdan: {text}</i>")
        
        process_user_message(message.chat.id, message.from_user.id, message.from_user.first_name, text)
        
    except Exception as e:
        logger.error(f"Voice handler xato: {e}", exc_info=True)
        try:
            bot.edit_message_text(
                "❌ Audio bilan ishlashda xato. Matn yozib yuboring.",
                chat_id=wait_msg.chat.id, message_id=wait_msg.message_id
            )
        except:
            pass
    finally:
        if os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception as e:
                logger.warning(f"Audio o'chirishda xato: {e}")


# --- Matnli xabarlar
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    process_user_message(message.chat.id, message.from_user.id, message.from_user.first_name, message.text)


# --- Asosiy mantiq
def process_user_message(chat_id: int, user_id: int, first_name: str, text: str):
    save_user(user_id, first_name)
    wait_msg = bot.send_message(chat_id, "⏳ <i>O'ylayapman...</i>")
    
    try:
        save_message(user_id, "user", text)
        
        history = get_recent_messages(user_id, limit=10)
        history = history[:-1] if history else []
        
        tasks, javob = generate_schedule(text, history)
        
        save_message(user_id, "assistant", javob)
        
        if len(history) >= 20:
            cleanup_old_messages(user_id, keep_last=50)
        
        if tasks:
            display = javob + "\n\n📅 <b>Rejaga qo'shildi:</b>\n\n"
            for t in tasks:
                display += f"⏰ <b>{t['sana_vaqt'].strftime('%d-%m %H:%M')}</b> — {t['vazifa']}\n"
                if t.get('maslahat'):
                    display += f"💡 <i>{t['maslahat']}</i>\n"
                display += "\n"
                save_task(user_id, t["vazifa"], t["sana_vaqt"])
            
            bot.edit_message_text(display, chat_id=wait_msg.chat.id, message_id=wait_msg.message_id)
        else:
            bot.edit_message_text(javob, chat_id=wait_msg.chat.id, message_id=wait_msg.message_id)
            
    except Exception as e:
        logger.error(f"process_user_message xato (user {user_id}): {e}", exc_info=True)
        try:
            bot.edit_message_text(
                "❌ Xatolik yuz berdi. Birozdan keyin urinib ko'ring.",
                chat_id=wait_msg.chat.id, message_id=wait_msg.message_id
            )
        except:
            pass


# --- Webhook
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        json_str = request.get_data().decode("UTF-8")
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return "OK", 200
    except Exception as e:
        logger.error(f"Webhook xato: {e}", exc_info=True)
        return "ERROR", 500


@app.route("/", methods=["GET"])
def health():
    return "VaqtUstasi bot is running!", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))