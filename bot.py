import os
import threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# 🔐 Telegram Bot Token
TOKEN = "8545902801:AAGjHYxHsb2J8Ui4zo0L4oPaKHWqawiMq30"

# --- Render sağlık kontrolü için mini web sunucusu ---
app = Flask(__name__)

@app.get("/")
def root():
    return "Bot running ✅"

# --- Telegram komutları ve mesaj yakalama ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Merhaba Ahmet! Bot aktif ✅")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("/start yaz; mesaj gönderirsen aynen geri yollarım.")

async def ping_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("pong 🏓")

async def echo_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        await update.message.reply_text(update.message.text)

def run_bot():
    # Yeni sürümde Application kullanılır (Updater kalktı)
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("ping", ping_cmd))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_msg))
    application.run_polling(allowed_updates=Update.ALL_TYPES)

def run_web():
    # Render, servis portunu PORT değişkeninden verir
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # Bot polling + Flask aynı anda çalışsın
    threading.Thread(target=run_bot, daemon=True).start()
    run_web()
