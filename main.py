import os
import time
import threading
import requests
from flask import Flask, request
from datetime import datetime

app = Flask(__name__)

TELEGRAM_TOKEN = "8778813479:AAEXWot8gPOMpuW0J3Fi2Z2jBcpltQwXHys"
API_KEY = "4d4a4dd9edcd8c6a8dc6b901d576b844"
CHAT_ID = "7306296182"
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
FOOTBALL_API = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

ALL_LEAGUES = [39,140,135,78,61,2,3,57,73,116,188,253,550,551,545,233,234,144,218]

alerted = {}

def send_msg(text):
    try:
        requests.post(f"{TELEGRAM_API}/sendMessage", json={
            "chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"
        }, timeout=10)
    except Exception as e:
        print(f"Error: {e}")

def send_to(chat_id, text):
    try:
        requests.post(f"{TELEGRAM_API}/sendMessage", json={
            "chat_id": chat_id, "text": text, "parse_mode": "HTML"
        }, timeout=10)
    except Exception as e:
        print(f"Error: {e}")

def fapi(endpoint):
    try:
        r = requests.get(f"{FOOTBALL_API}{endpoint}", headers=HEADERS, timeout=15)
        return r.json()
    except:
        return {"response": []}

def calc_prob(minute, total_goals, shots, corners):
    base = 50 * (0.4 + (max(0, 90 - minute) / 90) * 0.6)
    if shots >= 10: base += 15
    elif shots >= 6: base += 8
    elif shots >= 3: base += 3
    if corners >= 8: base += 10
    elif corners >= 5: base += 5
    elif corners >= 3: base += 2
    if total_goals >= 3: base += 10
    elif total_goals >= 2: base += 5
    elif total_goals == 0 and minute > 60: base -= 8
    if minute >= 80: base -= 12
    elif minute >= 70: base -= 5
    return min(95, max(5, round(base)))

def get_bets(prob, home, away, hg, ag, minute):
    bets = []
    total = hg + ag
    if prob >= 75 and total <= 1:
        bets.append(f"📈 Más de {total + 0.5} goles")
    if prob >= 65 and total >= 2:
        bets.append(f"📈 Más de {total - 0.5} goles")
    if prob >= 65:
        if hg > ag:
            bets.append(f"🏠 {home} gana (1)")
        elif ag > hg:
            bets.append(f"✈️ {away} gana (2)")
        else:
            bets.append("🤝 Ambos anotan (BTTS)")
    return bets

def scan_live():
    while True:
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Escaneando...")
            data = fapi("/fixtures?live=all")
            for f in data.get("response", []):
                fid = f["fixture"]["id"]
                minute = f["fixture"]["status"].get("elapsed") or 0
                home = f["teams"]["home"]["name"]
                away = f["teams"]["away"]["name"]
                hg = f["goals"]["home"] or 0
                ag = f["goals"]["away"] or 0
                league = f["league"]["name"]

                key = f"{fid}_{minute // 10}"
                if key in alerted:
                    continue

                stats = fapi(f"/fixtures/statistics?fixture={fid}").get("response", [])
                shots, corners = 0, 0
                if len(stats) >= 2:
                    def gs(team, name):
                        s = next((x for x in team["statistics"] if x["type"] == name), None)
                        return int(s["value"] or 0) if s and s["value"] else 0
                    shots = gs(stats[0], "Shots on Goal") + gs(stats[1], "Shots on Goal")
                    corners = gs(stats[0], "Corner Kicks") + gs(stats[1], "Corner Kicks")

                prob = calc_prob(minute, hg + ag, shots, corners)
                bets = get_bets(prob, home, away, hg, ag, minute)

                if bets and prob >= 65:
                    bets_text = "\n".join(bets)
                    msg = (
                        f"🚨 <b>OPORTUNIDAD - FÚTBOL</b>\n\n"
                        f"⚽ <b>{home} vs {away}</b>\n"
                        f"🏆 {league} | Min {minute}' | {hg}-{ag}\n\n"
                        f"💰 <b>QUÉ APOSTAR:</b>\n{bets_text}\n"
                        f"📈 <b>PROBABILIDAD:</b> {prob}%\n\n"
                        f"⚠️ Apuesta con responsabilidad."
                    )
                    send_msg(msg)
                    alerted[key] = True

            if len(alerted) > 1000:
                alerted.clear()
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(180)

def process_command(chat_id, text):
    cmd = text.strip().lower().split()[0]
    if cmd in ["/inicio", "/start"]:
        send_to(chat_id,
            "👋 <b>Bot de Fútbol</b>\n\n"
            "🤖 Te mando alertas automáticas de apuestas cuando hay oportunidad.\n\n"
            "📋 <b>Comandos:</b>\n"
            "/vivo - Partidos en vivo ahora\n"
            "/hoy - Partidos de hoy\n"
            "/ayuda - Todos los comandos"
        )
    elif cmd == "/vivo":
        data = fapi("/fixtures?live=all")
        fixtures = data.get("response", [])
        if not fixtures:
            send_to(chat_id, "⚽ No hay partidos en vivo ahora.")
            return
        msg = f"🔴 <b>{len(fixtures)} Partidos en Vivo</b>\n\n"
        for f in fixtures[:12]:
            msg += (f"⚽ {f['teams']['home']['name']} "
                   f"{f['goals']['home'] or 0}-{f['goals']['away'] or 0} "
                   f"{f['teams']['away']['name']}\n"
                   f"🏆 {f['league']['name']} | ⏱ {f['fixture']['status'].get('elapsed') or 0}'\n\n")
        send_to(chat_id, msg)
    elif cmd == "/hoy":
        today = datetime.now().strftime("%Y-%m-%d")
        data = fapi(f"/fixtures?date={today}")
        fixtures = data.get("response", [])
        if not fixtures:
            send_to(chat_id, "📅 No hay partidos hoy.")
            return
        msg = f"📅 <b>Partidos de Hoy ({len(fixtures)})</b>\n\n"
        for f in fixtures[:15]:
            hora = f["fixture"]["date"][11:16]
            msg += (f"⚽ {f['teams']['home']['name']} vs "
                   f"{f['teams']['away']['name']}\n"
                   f"🏆 {f['league']['name']} | 🕐 {hora}\n\n")
        send_to(chat_id, msg)
    elif cmd == "/ayuda":
        send_to(chat_id,
            "📋 <b>Comandos:</b>\n\n"
            "/inicio - Bienvenida\n"
            "/vivo - Partidos en vivo\n"
            "/hoy - Partidos de hoy\n"
            "/ayuda - Esta lista\n\n"
            "🚨 Las alertas llegan automáticamente."
        )

@app.route(f"/webhook/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    data = request.json
    if "message" in data:
        chat_id = str(data["message"]["chat"]["id"])
        text = data["message"].get("text", "")
        if text:
            process_command(chat_id, text)
    return "OK"

@app.route("/")
def home():
    return "⚽ Bot de Fútbol activo!"

@app.route("/health")
def health():
    return "OK"

def set_webhook():
    time.sleep(5)
    url = os.environ.get("RENDER_EXTERNAL_URL", "")
    if url:
        r = requests.post(f"{TELEGRAM_API}/setWebhook",
            json={"url": f"{url}/webhook/{TELEGRAM_TOKEN}"})
        print(f"Webhook: {r.json()}")

if __name__ == "__main__":
    print("⚽ Bot de Fútbol iniciado!")
    threading.Thread(target=scan_live, daemon=True).start()
    threading.Thread(target=set_webhook, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
