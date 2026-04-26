import os
import telebot
from flask import Flask, request
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from zoneinfo import ZoneInfo

from app.ai_service import generate_schedule
from app.database import init_db, save_user, save_task, get_pending_tasks, mark_reminded, mark_done

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

UZ_TZ = ZoneInfo("Asia/Tashkent")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=False)
app = Flask(__name__)

# --- Database ishga tushirish
init_db()

# --- Webhook o'rnatish
bot.remove_webhook()
bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
print("Webhook o'rnatildi!")


# --- Eslatma tizimi
def check_reminders():
    """Vaqti yetib kelgan vazifalarni tekshirish"""
    now_uz = datetime.now(UZ_TZ)
    print(f"Checking reminders at UZ time: {now_uz.strftime('%Y-%m-%d %H:%M')}")
    
    tasks = get_pending_tasks()
    
    for task in tasks:
        try:
            scheduled = task["scheduled_time"]
            time_str = scheduled.strftime("%H:%M")
            
            bot.send_message(
                task["user_id"],
                f"⏰ <b>Eslatma!</b>\n\n"
                f"Soat <b>{time_str}</b> bo'ldi.\n"
                f"📌 <b>{task['task_text']}</b>\n\n"
                f"Bajardingizmi?",
                reply_markup=done_keyboard(task["id"])
            )
            mark_reminded(task["id"])
        except Exception as e:
            print(f"REMINDER ERROR: {e}")


def done_keyboard(task_id):
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(
        telebot.types.InlineKeyboardButton("✅ Ha, bajardim!", callback_data=f"done_{task_id}"),
        telebot.types.InlineKeyboardButton("❌ Hali yo'q", callback_data=f"skip_{task_id}")
    )
    return keyboard


# Har daqiqada eslatmalarni tekshirish
scheduler = BackgroundScheduler()
scheduler.add_job(check_reminders, "interval", minutes=1)
scheduler.start()


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
        bot.process_new_updates([update])
    except Exception as e:
        print(f"WEBHOOK ERROR: {type(e).__name__}: {e}")
    return "OK", 200


# --- HANDLERS

@bot.message_handler(commands=["start"])
def start(message):
    save_user(message.from_user.id, message.from_user.first_name)
    bot.send_message(
        message.chat.id,
        f"👋 <b>Salom, {message.from_user.first_name}!</b>\n\n"
        "Men VaqtUstasi AI — sizning shaxsiy vaqt menejeringizman.\n\n"
        "📅 Kunlik reja tuzaman\n"
        "⏰ Vazifa vaqti kelganda eslataman\n"
        "✅ Bajardingizmi deb so'rayman\n\n"
        "✍️ Vazifangizni yozing:\n"
        "<i>Masalan: Ertaga soat 7da sport, bugun 19da ingliz tili</i>"
    )


@bot.message_handler(commands=["help"])
def help_command(message):
    bot.send_message(
        message.chat.id,
        "📌 <b>Qanday foydalaniladi:</b>\n\n"
        "Vazifalarni oddiy yozing:\n\n"
        "• Bugun 1 soat sport\n"
        "• Ertaga 19:00 uchrashuv\n"
        "• Juma kuni 14da hisobot\n"
        "• 3 kundan keyin 10da yig'ilish\n\n"
        "Men sizga optimal vaqt reja tuzib beraman 📅"
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("done_"))
def handle_done(call):
    task_id = int(call.data.split("_")[1])
    mark_done(task_id)
    bot.edit_message_text(
        "✅ <b>Barakalla! Vazifani bajardingiz!</b>\n\nDavom eting, siz zo'rsiz! 💪",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("skip_"))
def handle_skip(call):
    task_id = int(call.data.split("_")[1])
    bot.edit_message_text(
        "💪 <b>Hali ham vaqt bor!</b>\n\nVazifani bajarishga harakat qiling!",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )


@bot.message_handler(func=lambda message: True)
def handle_task(message):
    save_user(message.from_user.id, message.from_user.first_name)
    user_text = message.text

    wait_msg = bot.send_message(
        message.chat.id,
        "⏳ <i>VaqtUstasi o'ylayapti...</i>"
    )

    try:
        tasks, display = generate_schedule(user_text)

        if tasks:
            bot.edit_message_text(
                f"📅 <b>Sizning rejangiz:</b>\n\n{display}"
                f"✅ Vazifa vaqti kelganda eslataman!",
                chat_id=wait_msg.chat.id,
                message_id=wait_msg.message_id
            )
            for task in tasks:
                save_task(message.from_user.id, task["vazifa"], task["sana_vaqt"])
        else:
            # Suhbat rejimi
            bot.edit_message_text(
                display,
                chat_id=wait_msg.chat.id,
                message_id=wait_msg.message_id
            )

    except Exception as e:
        print(f"HANDLER ERROR: {type(e).__name__}: {e}")
        bot.edit_message_text(
            "❌ Xatolik bo'ldi. Qayta urinib ko'ring.",
            chat_id=wait_msg.chat.id,
            message_id=wait_msg.message_id
        )