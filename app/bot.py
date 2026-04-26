import os
import telebot
from flask import Flask, request
from dotenv import load_dotenv
from app.ai_service import generate_schedule

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

print(f"BOT_TOKEN: {'OK' if BOT_TOKEN else 'NONE!'}")
print(f"WEBHOOK_URL: {WEBHOOK_URL}")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=False)
app = Flask(__name__)


# --- ROUTES

@app.route("/", methods=["GET"])
def health():
    return "VaqtUstasi is running 🚀", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("UTF-8")
    if not json_str:
        return "OK", 200
    try:
        update = telebot.types.Update.de_json(json_str)
        print(f"UPDATE TEXT: {update.message.text if update.message else 'no text'}")
        bot.process_new_updates([update])
        print("PROCESS DONE")
    except Exception as e:
        print(f"WEBHOOK ERROR: {type(e).__name__}: {e}")
    return "OK", 200


@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    bot.remove_webhook()
    result = bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")  # ← to'g'ri
    return f"Webhook set: {result}", 200


# --- HANDLERS

@bot.message_handler(commands=["start"])
def start(message):
    try:
        bot.send_message(
            message.chat.id,
            "👋 <b>Salom, men VaqtUstasi AI!</b>\n\n"
            "Men sizning shaxsiy vaqt menejeringizman.\n\n"
            "📅 Kunlik reja tuzaman\n"
            "⏰ Vazifalarni vaqtga joylayman\n"
            "🎯 Intizomni oshirishga yordam beraman\n\n"
            "✍️ Vazifangizni yozing:\n"
            "<i>Masalan:</i>\n"
            "👉 Ertaga 2 soat ingliz tili\n"
            "👉 Bugun 1 soat sport"
        )
        print("START MESSAGE SENT")
    except Exception as e:
        print(f"START ERROR: {type(e).__name__}: {e}")

@bot.message_handler(commands=["help"])
def help_command(message):
    bot.send_message(
        message.chat.id,
        "📌 <b>Qanday foydalaniladi:</b>\n\n"
        "Vazifani oddiy yozing:\n\n"
        "• Bugun 1 soat sport\n"
        "• Ertaga 19:00 uchrashuv\n"
        "• Har kuni 30 min kitob o'qish\n\n"
        "Men sizga optimal vaqt reja tuzib beraman 📅"
    )


@bot.message_handler(func=lambda message: True)
def handle_task(message):
    print(f"HANDLER CALLED: {message.chat.id}")
    bot.send_message(message.chat.id, "Test xabar")
    print("SENT!")