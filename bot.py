# bot.py
import os
import threading
import requests
from datetime import datetime
from flask import Flask
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)

# === AYARLAR ===
TOKEN = "8545902801:AAGjHYxHsb2J8Ui4zo0L4oPaKHWqawiMq30"   # Telegram bot token
API_FOOTBALL_KEY = "b1527d8aed049717409f0e0b37751d26"      # API-FOOTBALL key
API_BASE = "https://v3.football.api-sports.io"
API_TZ = "Europe/Istanbul"  # Listelemeyi TR saatine göre yapalım

# Chat bazlı son listeyi tutacağız: {chat_id: [fixtures]}
LAST_LIST: dict[int, list[dict]] = {}

# ---- Render healtcheck için mini web ----
app = Flask(__name__)

@app.get("/")
def root():
    return "Bot running ✅"

@app.get("/healthz")
def healthz():
    return "ok"

# ---- Yardımcılar ----
def fetch_fixtures(date_str: str) -> list[dict]:
    """
    Belirli bir tarihteki maçları döndürür (liste).
    Her eleman: {home, away, time, league, fixture_id}
    """
    url = f"{API_BASE}/fixtures"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    params = {"date": date_str, "timezone": API_TZ}

    r = requests.get(url, headers=headers, params=params, timeout=20)
    r.raise_for_status()
    js = r.json()

    results = []
    for item in js.get("response", []):
        league = item.get("league", {}).get("name", "")
        home = item.get("teams", {}).get("home", {}).get("name", "")
        away = item.get("teams", {}).get("away", {}).get("name", "")
        # Saat
        utc = item.get("fixture", {}).get("date", "")
        try:
            dt = datetime.fromisoformat(utc.replace("Z", "+00:00"))
            time_str = dt.astimezone().strftime("%H:%M")
        except Exception:
            time_str = "-"
        results.append({
            "home": home,
            "away": away,
            "time": time_str,
            "league": league,
            "fixture_id": item.get("fixture", {}).get("id"),
        })
    return results

def fmt_list(fixtures: list[dict]) -> str:
    if not fixtures:
        return "❌ Bu tarihte maç bulunamadı."
    lines = []
    for i, f in enumerate(fixtures, 1):
        lines.append(f"{i:>2}. {f['time']}  {f['home']} – {f['away']}  ({f['league']})")
    return "📅 Maçlar:\n" + "\n".join(lines)

# ---- Komutlar ----
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Merhaba Ahmet! Bot aktif ✅\n\n"
        "⚽️ İddia Botu aktif!\n"
        "• Gün maç listesi: /list YYYY-MM-DD (örn: /list 2025-12-10)\n"
        "• Listeden maç seç: /pick N (örn: /pick 1)"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Komutlar:\n"
        "/list YYYY-MM-DD  → O günün maçlarını getirir\n"
        "/pick N            → Son listeden N. maçı seçip temel analiz verir\n"
        "/ping              → Test"
    )

async def ping_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("pong 🏓")

async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /list 2025-12-10
    if not context.args:
        await update.message.reply_text("Tarih ver: /list YYYY-MM-DD")
        return
    date_str = context.args[0]
    try:
        # basit doğrulama
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        await update.message.reply_text("Tarih formatı yanlış. Örnek: /list 2025-12-10")
        return

    try:
        fixtures = fetch_fixtures(date_str)
    except Exception as e:
        await update.message.reply_text(f"⚠️ API hatası: {e}")
        return

    # chat bazında sakla
    chat_id = update.effective_chat.id
    LAST_LIST[chat_id] = fixtures

    await update.message.reply_text(fmt_list(fixtures))

async def pick_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /pick 1
    chat_id = update.effective_chat.id
    fixtures = LAST_LIST.get(chat_id, [])
    if not fixtures:
        await update.message.reply_text("Önce bir liste getir: /list YYYY-MM-DD")
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Kullanım: /pick N  (örn: /pick 1)")
        return

    idx = int(context.args[0]) - 1
    if idx < 0 or idx >= len(fixtures):
        await update.message.reply_text("Geçersiz seçim.")
        return

    f = fixtures[idx]
    # Basit “form” örneği: iki takımın son maç sayısı & golleri (özet)
    # Free planda minimal tutuyoruz; istersen ileride H2H ve son 10 maç ekleriz.
    text = (
        "🔎 Seçim:\n"
        f"• {f['home']} – {f['away']}\n"
        f"• Saat: {f['time']}  • Lig: {f['league']}\n"
        "📌 Ayrıntılı analiz modüllerini ekleyeceğiz."
    )
    await update.message.reply_text(text)

async def echo_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        await update.message.reply_text(update.message.text)

# ---- Çalıştırma ----
def run_bot():
    app_ = Application.builder().token(TOKEN).build()
    app_.add_handler(CommandHandler("start", start_cmd))
    app_.add_handler(CommandHandler("help", help_cmd))
    app_.add_handler(CommandHandler("ping", ping_cmd))
    app_.add_handler(CommandHandler("list", list_cmd))
    app_.add_handler(CommandHandler("pick", pick_cmd))
    app_.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_msg))
    app_.run_polling(allowed_updates=Update.ALL_TYPES)

def run_web():
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    run_web()
