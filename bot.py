import os
import threading
import time
import json
from typing import List, Dict, Any

import requests
from flask import Flask
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters
)

# =======================
# 🔐 AYARLAR
# =======================

# Telegram BOT token (istersen Render'da ENV ile de verebilirsin: TOKEN)
TOKEN = os.getenv(
    "TOKEN",
    "8545902801:AAGjHYxHsb2J8Ui4zo0L4oPaKHWqawiMq30"  # senin verdiğin token
)

# API-FOOTBALL (API-SPORTS) anahtarın
API_KEY = os.getenv(
    "API_FOOTBALL_KEY",
    "b1527d8aed049717409f0e0b37751d26"  # senin verdiğin key
)

# Saat dilimi (API'den dönen maç saatleri için)
TZ = os.getenv("TZ", "Europe/Istanbul")

# API v3 ana URL
API_BASE = "https://v3.football.api-sports.io"

# Chat bazlı son liste cache’i ( /pick için )
LAST_LISTS: Dict[int, List[Dict[str, Any]]] = {}

# =======================
# 🌐 Mini web sunucu (Render health check için)
# =======================
app = Flask(__name__)

@app.get("/")
def root():
    return "İddaa Botu çalışıyor ✅"

@app.get("/healthz")
def health():
    return "ok", 200

# =======================
# 🔧 Yardımcılar
# =======================

def api_get(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """API-FOOTBALL GET isteği + loglar."""
    url = f"{API_BASE}{path}"
    headers = {"x-apisports-key": API_KEY}
    print(f"🌍 GET {url} params={params}")
    r = requests.get(url, headers=headers, params=params, timeout=30)
    print(f"🛰️  API status={r.status_code}")
    try:
        data = r.json()
    except Exception:
        print("⚠️ JSON parse edilemedi, text:", r.text[:500])
        raise
    # kısa özet log
    print("🧾 API snippet:", json.dumps(data, ensure_ascii=False)[:400])
    return data

def fetch_fixtures(date_str: str) -> List[Dict[str, Any]]:
    """Belirli bir günde oynanan/oynanacak maçlar (fixtures)."""
    print(f"📅 API'den veri çekiliyor: {date_str}")
    data = api_get("/fixtures", {"date": date_str, "timezone": TZ})
    results = data.get("response", []) or []
    print(f"🔍 API yanıtı: {len(results)} maç bulundu")
    matches = []
    for fx in results:
        try:
            matches.append({
                "fixture_id": fx["fixture"]["id"],
                "timestamp": fx["fixture"]["timestamp"],
                "league": fx["league"]["name"],
                "country": fx["league"]["country"],
                "home_name": fx["teams"]["home"]["name"],
                "home_id": fx["teams"]["home"]["id"],
                "away_name": fx["teams"]["away"]["name"],
                "away_id": fx["teams"]["away"]["id"],
                "status": fx["fixture"]["status"]["short"],
                "datetime": fx["fixture"]["date"],
            })
        except KeyError:
            # beklenmedik alanlar olursa sessizce geç
            continue
    return matches

def fetch_last_form(team_id: int, last: int = 5) -> Dict[str, Any]:
    """
    Takımın son maçlarına hızlı bakış (form).
    NOTE: Ücretsiz planda tüm ligler/her endpoint limitli olabilir; hata olursa tolere ediyoruz.
    """
    try:
        data = api_get("/fixtures", {"team": team_id, "last": last, "timezone": TZ})
        games = data.get("response", []) or []
        w = d = l = gf = ga = 0
        for g in games:
            home = g["teams"]["home"]
            away = g["teams"]["away"]
            goals = g["goals"]
            # gol sayıları
            gf += goals["for"] if "for" in goals else (goals["home"] if home["id"] == team_id else goals["away"])
            ga += goals["against"] if "against" in goals else (goals["away"] if home["id"] == team_id else goals["home"])
            # sonuç
            if home["id"] == team_id:
                if home["winner"] is True:
                    w += 1
                elif away["winner"] is True:
                    l += 1
                else:
                    d += 1
            else:
                if away["winner"] is True:
                    w += 1
                elif home["winner"] is True:
                    l += 1
                else:
                    d += 1
        return {"w": w, "d": d, "l": l, "gf": gf, "ga": ga, "n": len(games)}
    except Exception as e:
        print(f"⚠️ fetch_last_form hata: {e}")
        return {"w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0, "n": 0}

def format_match_line(i: int, m: Dict[str, Any]) -> str:
    lg = m["league"]
    cn = m["country"]
    return f"{i}. {m['home_name']} — {m['away_name']}  ({lg}, {cn})"

# =======================
# 🤖 Telegram komutları
# =======================

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "⚽ İddaa Botu aktif!\n"
        f"• Gün maç listesi: /list 2025-12-10\n"
        f"• Listeden maç seç: /pick 1\n"
        f"• Saat dilimi: {TZ}\n"
    )
    await update.message.reply_text(text)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Komutlar:\n"
        "• /list YYYY-MM-DD → Günün maçları\n"
        "• /pick N → Listeden N. maçı analiz et\n"
    )
    await update.message.reply_text(text)

async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    args = context.args or []
    if not args:
        await update.message.reply_text("Kullanım: /list YYYY-MM-DD")
        return
    date_str = args[0].strip()
    try:
        matches = fetch_fixtures(date_str)
    except Exception as e:
        print("❌ /list hatası:", e)
        await update.message.reply_text("❌ Maçlar alınamadı. Biraz sonra tekrar dene.")
        return

    if not matches:
        await update.message.reply_text("❌ Bu tarihte maç bulunamadı.")
        return

    LAST_LISTS[chat_id] = matches
    lines = [f"📅 {date_str} için maçlar ({len(matches)}):"]
    for i, m in enumerate(matches, start=1):
        lines.append(format_match_line(i, m))
        if i >= 30:  # çok uzamasın
            lines.append(f"... ve {len(matches)-30} maç daha")
            break
    await update.message.reply_text("\n".join(lines))

async def pick_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    args = context.args or []
    if chat_id not in LAST_LISTS:
        await update.message.reply_text("Önce /list ile maçları getir, sonra /pick N yaz.")
        return
    if not args:
        await update.message.reply_text("Kullanım: /pick N  (ör: /pick 1)")
        return
    try:
        idx = int(args[0])
    except ValueError:
        await update.message.reply_text("N sayısı geçersiz. (ör: /pick 1)")
        return

    matches = LAST_LISTS[chat_id]
    if idx < 1 or idx > len(matches):
        await update.message.reply_text("Listedeki sıra numarasını gir. (ör: /pick 1)")
        return

    m = matches[idx - 1]
    # temel analiz (son 5 maç formu)
    h_form = fetch_last_form(m["home_id"], last=5)
    a_form = fetch_last_form(m["away_id"], last=5)

    def form_text(name: str, f: Dict[str, Any]) -> str:
        if f["n"] == 0:
            return f"{name}: Son maçlar bulunamadı."
        return f"{name}: {f['w']}G-{f['d']}B-{f['l']}M | {f['gf']}⚽ atıp {f['ga']}⚽ yedi (son {f['n']})"

    reply = (
        f"🎯 *Seçilen Maç*\n"
        f"{m['home_name']} — {m['away_name']}  \n"
        f"🏆 {m['league']} ({m['country']})\n\n"
        f"{form_text(m['home_name'], h_form)}\n"
        f"{form_text(m['away_name'], a_form)}\n"
        f"\n"
        f"📝 İpucu: Formu daha iyi olan tarafa (özellikle iç sahada) eğilimli ol.\n"
        f"Not: Bu istatistik bilgilendirme amaçlıdır."
    )
    await update.message.reply_text(reply, parse_mode="Markdown")

async def echo_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Bot gereksiz her şeyi tekrarlamasın; sadece komut dışı kısa cevap
    if update.message and update.message.text:
        await update.message.reply_text("Komutları görmek için /help yaz.")

# =======================
# 🚀 Çalıştırma
# =======================

def run_bot():
    print("✅ Bot başlıyor...")
    print(f"   TZ={TZ}")
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("list", list_cmd))
    application.add_handler(CommandHandler("pick", pick_cmd))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_msg))

    # polling (thread içinde)
    application.run_polling(allowed_updates=Update.ALL_TYPES)

def run_web():
    port = int(os.environ.get("PORT", "10000"))
    print(f"🌐 Flask health server port={port} ile açılıyor...")
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # Hem bot hem web aynı anda
    threading.Thread(target=run_bot, daemon=True).start()
    # küçük gecikme; event loop hazırlansın
    time.sleep(1)
    run_web()
