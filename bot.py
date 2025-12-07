import os
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = "8545902801:AAGjHYxHsb2J8Ui4zo0L4oPaKHWqawiMq30"

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot running ✅"

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Merhaba Ahmet! Bot aktif ✅")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("/start yaz; mesaj gönderirsen aynen geri yollarım.")

async def ping_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("pong 🏓")

async def echo_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        await update.message.reply_text(update.message.text)

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

def run_telegram():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("ping", ping_cmd))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_msg))
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    Thread(target=run_flask).start()
    run_telegram()
