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
    mark_reminded, mark_done, save_message, get_recent_messages,
    cleanup_old_messages
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


# --- Eslatmalar
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


def done_keyboard(task_id):
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(
        telebot.types.InlineKeyboardButton("✅ Bajardim", callback_data=f"done_{task_id}"),
        telebot.types.InlineKeyboardButton("❌ Yo'q", callback_data=f"skip_{task_id}")
    )
    return keyboard


scheduler = BackgroundScheduler(timezone=UZ_TZ)
scheduler.add_job(check_reminders, "interval", minutes=1)
scheduler.start()


# --- Callback (Bajardim/Yo'q tugmalari)
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        action, task_id = call.data.split("_", 1)
        task_id = int(task_id)
        
        if action == "done":
            mark_done(task_id)
            bot.answer_callback_query(call.id, "✅ Ajoyib!")
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        elif action == "skip":
            bot.answer_callback_query(call.id, "Mayli, keyin urinib ko'ring")
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    except Exception as e:
        logger.error(f"Callback xato: {e}", exc_info=True)


# --- Ovozli xabarlar
@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    wait_msg = bot.send_message(message.chat.id, "🎤 <i>Eshityapman...</i>")
    
    # Unique fayl nomi (har foydalanuvchi uchun alohida)
    audio_path = os.path.join(AUDIO_DIR, f"{message.from_user.id}_{uuid.uuid4().hex}.ogg")
    
    try:
        # Audio yuklab olish
        file_info = bot.get_file(message.voice.file_id)
        downloaded = bot.download_file(file_info.file_path)
        
        with open(audio_path, "wb") as f:
            f.write(downloaded)
        
        # Transkripsiya
        text = transcribe_audio(audio_path)
        
        if not text:
            bot.edit_message_text(
                "❌ Audio aniqlanmadi. Iltimos, qaytadan urinib ko'ring yoki matn yozing.",
                chat_id=wait_msg.chat.id, message_id=wait_msg.message_id
            )
            return
        
        # Wait xabarini o'chirish
        bot.delete_message(message.chat.id, wait_msg.message_id)
        
        # Transkripsiyani foydalanuvchiga ko'rsatish (shaffoflik uchun)
        bot.send_message(message.chat.id, f"🎤 <i>Sizdan: {text}</i>")
        
        # AI'ga yuborish
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
        # Audio faylni o'chirish (disk to'lmasligi uchun)
        if os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception as e:
                logger.warning(f"Audio o'chirishda xato: {e}")


# --- Matnli xabarlar
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    process_user_message(message.chat.id, message.from_user.id, message.from_user.first_name, message.text)


# --- Asosiy mantiq (matn va audio uchun bitta funksiya)
def process_user_message(chat_id: int, user_id: int, first_name: str, text: str):
    save_user(user_id, first_name)
    wait_msg = bot.send_message(chat_id, "⏳ <i>O'ylayapman...</i>")
    
    try:
        # Foydalanuvchi xabarini bazaga saqlash
        save_message(user_id, "user", text)
        
        # Kontekst (oldingi xabarlar)
        history = get_recent_messages(user_id, limit=10)
        # Yangi xabarni history'dan chiqarib tashlash (u allaqachon save_message orqali qo'shildi)
        history = history[:-1] if history else []
        
        # AI'dan javob olish
        tasks, javob = generate_schedule(text, history)
        
        # Bot javobini bazaga saqlash
        save_message(user_id, "assistant", javob)
        
        # Eski xabarlarni tozalash (har 10 ta xabardan keyin)
        if len(history) >= 20:
            cleanup_old_messages(user_id, keep_last=50)
        
        # Vazifalarni saqlash va ko'rsatish
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
