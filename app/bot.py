import os
import telebot
from flask import Flask, request
from dotenv import load_dotenv
from app.ai_service import generate_schedule

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

# --- ROUTES

@app.route("/", methods=["GET"])
def health():
    return "VaqtUstasi is running 🚀", 200


@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200


@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    bot.remove_webhook()
    bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
    return "Webhook set!", 200


# --- HANDLERS

@bot.message_handler(commands=['start'])
def start(message):
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


@bot.message_handler(commands=['help'])
def help_command(message):
    bot.send_message(
        message.chat.id,
        "📌 <b>Qanday foydalaniladi:</b>\n\n"
        "Vazifani oddiy yozing:\n\n"
        "• Bugun 1 soat sport\n"
        "• Ertaga 19:00 uchrashuv\n"
        "• Har kuni 30 min kitob o‘qish\n\n"
        "Men sizga optimal vaqt reja tuzib beraman 📅"
    )


@bot.message_handler(func=lambda message: True)
def handle_task(message):
    user_text = message.text

    wait_msg = bot.send_message(
        message.chat.id,
        "⏳ <i>VaqtUstasi rejalashtiryapti...</i>"
    )

    try:
        result = generate_schedule(user_text)

        bot.edit_message_text(
            f"📅 <b>Sizning rejangiz:</b>\n\n{result}",
            chat_id=wait_msg.chat.id,
            message_id=wait_msg.message_id
        )

    except Exception as e:
        bot.edit_message_text(
            "❌ Xatolik bo‘ldi. Qayta urinib ko‘ring.",
            chat_id=wait_msg.chat.id,
            message_id=wait_msg.message_id
        )
        print("ERROR:", e)