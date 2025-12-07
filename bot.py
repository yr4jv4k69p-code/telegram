import os, threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = "8545902801:AAGjHYxHsb2J8Ui4zo0L4oPaKHWqawiMq30"

# Render'ın port health-check'i için mini web sunucu
app = Flask(__name__)

@app.get("/")
def root():
    return "Bot running ✅"

# ---- Telegram bot handler'ları ----
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Merhaba Ahmet! Bot aktif ✅")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("/start yaz; mesaj gönderirsen aynen geri yollarım.")

async def echo_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        await update.message.reply_text(update.message.text)

def run_bot():
    app_ = Application.builder().token(TOKEN).build()
    app_.add_handler(CommandHandler("start", start_cmd))
    app_.add_handler(CommandHandler("help", help_cmd))
    app_.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_msg))
    app_.run_polling(allowed_updates=Update.ALL_TYPES)

def run_web():
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    run_web()
