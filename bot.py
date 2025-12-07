import os
import requests
from datetime import datetime
from collections import defaultdict
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- AYARLAR (senin verdiğin anahtarlar) ---
TOKEN = "8545902801:AAGjHYxHsb2J8Ui4zo0L4oPaKHWqawiMq30"  # Telegram bot token
API_KEY = "b1527d8aed049717409f0e0b37751d26"              # API-FOOTBALL key

API_BASE = "https://v3.football.api-sports.io"
HDRS = {"x-apisports-key": API_KEY}

# Her kullanıcı için son /list sonucunu hafızada tutalım
user_last_list = defaultdict(list)  # user_id -> [fixture_dict, ...]

def fmt_time(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z","+00:00"))
        return dt.strftime("%H:%M")
    except Exception:
        return iso[11:16]

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚽ İddia Botu aktif!\n"
        "• Gün maç listesi: /list 2025-12-10\n"
        "• Listeden maç seç: /pick 1"
    )

async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("📅 Tarih gir: /list YYYY-MM-DD")
        return
    date = context.args[0]

    # Maçları çek
    url = f"{API_BASE}/fixtures?date={date}"
    try:
        r = requests.get(url, headers=HDRS, timeout=20)
        data = r.json()
    except Exception as e:
        await update.message.reply_text(f"⚠️ Ağ hatası: {e}")
        return

    fixtures = data.get("response", [])
    if not fixtures:
        await update.message.reply_text("❌ Bu tarihte maç bulunamadı.")
        return

    # Kullanıcıya özel olarak listeyi sakla
    uid = update.effective_user.id
    user_last_list[uid] = fixtures

    # Mesajı hazırla (ilk 20 maç)
    lines = [f"📅 {date} maçları (ilk {min(20,len(fixtures))} gösteriliyor):\n"]
    for i, fx in enumerate(fixtures[:20], start=1):
        league = fx["league"]["name"]
        home = fx["teams"]["home"]["name"]
        away = fx["teams"]["away"]["name"]
        tm = fmt_time(fx["fixture"]["date"])
        lines.append(f"{i}. 🕒 {tm} — {home} vs {away}  | 🏆 {league}")
    lines.append("\nBirini seç: /pick <numara>  (ör: /pick 1)")
    await update.message.reply_text("\n".join(lines))

def team_last5(team_id: int):
    """Takımın son 5 maçını ve küçük özetini döndürür."""
    url = f"{API_BASE}/fixtures?team={team_id}&last=5"
    r = requests.get(url, headers=HDRS, timeout=20)
    resp = r.json().get("response", [])

    gf = ga = w = d = l = 0
    for fx in resp:
        home_id = fx["teams"]["home"]["id"]
        hs = fx["goals"]["home"] or 0
        as_ = fx["goals"]["away"] or 0
        if home_id == team_id:
            gf += hs; ga += as_
            won = hs > as_
        else:
            gf += as_; ga += hs
            won = as_ > hs
        if hs == as_:
            d += 1
        elif won:
            w += 1
        else:
            l += 1
    return {"gf": gf, "ga": ga, "w": w, "d": d, "l": l}

async def pick_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in user_last_list or not user_last_list[uid]:
        await update.message.reply_text("Önce liste al: /list YYYY-MM-DD")
        return
    if not context.args:
        await update.message.reply_text("Numara gir: /pick 1")
        return

    try:
        idx = int(context.args[0]) - 1
    except ValueError:
        await update.message.reply_text("Geçersiz numara. Örn: /pick 1")
        return

    fixtures = user_last_list[uid]
    if idx < 0 or idx >= len(fixtures):
        await update.message.reply_text("Listede böyle bir numara yok.")
        return

    fx = fixtures[idx]
    league = fx["league"]["name"]
    home = fx["teams"]["home"]["name"]
    away = fx["teams"]["away"]["name"]
    hid = fx["teams"]["home"]["id"]
    aid = fx["teams"]["away"]["id"]
    tm = fmt_time(fx["fixture"]["date"])

    # Basit analiz: iki takımın son 5 maç özeti
    try:
        h5 = team_last5(hid)
        a5 = team_last5(aid)
    except Exception as e:
        await update.message.reply_text(f"Analiz hatası: {e}")
        return

    msg = (
        f"🎯 Seçilen Maç: {home} vs {away}\n"
        f"🏆 {league} | 🕒 {tm}\n\n"
        f"📊 SON 5 MAÇ ÖZETİ\n"
        f"{home}: {h5['w']}-{h5['d']}-{h5['l']}  | G/A: {h5['gf']}/{h5['ga']}\n"
        f"{away}: {a5['w']}-{a5['d']}-{a5['l']}  | G/A: {a5['gf']}/{a5['ga']}\n"
    )

    # Minik öneri (çok basit sezgi: form ve g/a farkı)
    home_score = h5['w']*3 + h5['d'] + (h5['gf']-h5['ga'])
    away_score = a5['w']*3 + a5['d'] + (a5['gf']-a5['ga'])
    if home_score - away_score >= 2:
        pick = "Ev sahibi (DÇ 1) eğilim"
    elif away_score - home_score >= 2:
        pick = "Deplasman (DÇ 2) eğilim"
    else:
        pick = "KG Var / 1X değerlendirilir"

    msg += f"\n📝 İlk bakış önerisi: {pick}"
    await update.message.reply_text(msg)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("list", list_cmd))
    app.add_handler(CommandHandler("pick", pick_cmd))
    app.run_polling()

if __name__ == "__main__":
    main()
  
