import os
import telebot
from flask import Flask, request
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from zoneinfo import ZoneInfo
from openai import OpenAI

from app.ai_service import generate_schedule
from app.database import init_db, save_user, save_task, get_pending_tasks, mark_reminded, mark_done

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
UZ_TZ = ZoneInfo("Asia/Tashkent")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=False)
app = Flask(__name__)

init_db()

# --- Eslatmalar funksiyasi
def check_reminders():
    tasks = get_pending_tasks()
    for task in tasks:
        try:
            bot.send_message(
                task["user_id"],
                f"⏰ <b>Vaqt bo'ldi!</b>\n\n📌 {task['task_text']}\n\nBajardingizmi?",
                reply_markup=done_keyboard(task["id"])
            )
            mark_reminded(task["id"])
        except: pass

def done_keyboard(task_id):
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(
        telebot.types.InlineKeyboardButton("✅ Bajardim", callback_data=f"done_{task_id}"),
        telebot.types.InlineKeyboardButton("❌ Yo'q", callback_data=f"skip_{task_id}")
    )
    return keyboard

# Har daqiqada tekshirish
scheduler = BackgroundScheduler()
scheduler.add_job(check_reminders, "interval", minutes=1)
scheduler.start()

# --- Ovozli xabarlarni handle qilish (OpenAI Whisper)
@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    wait_msg = bot.send_message(message.chat.id, "🎤 <i>Eshityapman...</i>")
    file_info = bot.get_file(message.voice.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    with open("voice.ogg", "wb") as f:
        f.write(downloaded_file)
        
    with open("voice.ogg", "rb") as audio_file:
        transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
    
    message.text = transcript.text
    bot.delete_message(message.chat.id, wait_msg.message_id)
    handle_task(message)

# --- Matnli xabarlar
@bot.message_handler(func=lambda message: True)
def handle_task(message):
    save_user(message.from_user.id, message.from_user.first_name)
    wait_msg = bot.send_message(message.chat.id, "⏳ <i>O'ylayapman...</i>")
    
    try:
        tasks, display = generate_schedule(message.text)
        
        if tasks:
            # Agar vazifalar bo'lsa, chiroyli qilib ko'rsatamiz
            clean_display = ""
            for t in tasks:
                clean_display += f"⏰ <b>{t['sana_vaqt'].strftime('%H:%M')}</b> - {t['vazifa']}\n💡 {t.get('maslahat','')}\n\n"
                save_task(message.from_user.id, t["vazifa"], t["sana_vaqt"])
            
            bot.edit_message_text(f"📅 <b>Yangi reja:</b>\n\n{clean_display}", 
                                  chat_id=wait_msg.chat.id, message_id=wait_msg.message_id)
        else:
            bot.edit_message_text(display, chat_id=wait_msg.chat.id, message_id=wait_msg.message_id)
            
    except Exception as e:
        bot.edit_message_text("❌ Xatolik yuz berdi.", chat_id=wait_msg.chat.id, message_id=wait_msg.message_id)

# --- Flask Routes
@app.route("/webhook", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

if __name__ == "__main__":
    app.run(port=5000)