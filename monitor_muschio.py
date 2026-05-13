#!/usr/bin/env python3
"""
=============================================================================
TPI MUSCHIO — Bot Telegram + Bridge MQTT (bot_muschio.py)
=============================================================================
Funzionalità:
  - Riceve i dati dall'ESP32 via HiveMQ Cloud e li invia su Telegram
  - Comandi disponibili nel bot:
      /start    — messaggio di benvenuto
      /stato    — richiede un campionamento (mostra ultimi dati ricevuti)
      /delay N  — imposta il delay di campionamento a N minuti
      /help     — lista comandi
  - Salva i dati in log_muschio.csv

Prerequisiti:
  pip install paho-mqtt python-telegram-bot

Uso:
  python monitor_muschio.py
=============================================================================
"""

import json
import csv
import os
import logging
import threading
from datetime import datetime

import paho.mqtt.client as mqtt
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes
)

# =============================================================================
# CONFIG — Modifica questi valori
# =============================================================================

# Telegram
TELEGRAM_TOKEN   = "8755285010:AAHvqt-ZDa-89-vn3ry_ujlWyupDNFkzohk"   # Token da @BotFather
TELEGRAM_CHAT_ID = None  # Viene impostato automaticamente al primo /start

# HiveMQ Cloud
MQTT_HOST = "69f128f236014b8689ffec3406c3f58d.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "Muschio"
MQTT_PASS = "Muschio32"

# Topic
TOPIC_DATI     = "progetto/muschio/dati"
TOPIC_COMANDO  = "progetto/muschio/comando"
TOPIC_STATUS   = "progetto/muschio/status"

# CSV
CSV_FILENAME = "log_muschio.csv"

# =============================================================================
# STATO GLOBALE
# =============================================================================
ultimi_dati: dict = {}          # Ultimi dati ricevuti dall'ESP32
telegram_app = None             # Riferimento all'app Telegram (impostato nel main)
chat_id_registrati: set = set() # Chat ID autorizzati (tutti quelli che fanno /start)
invio_automatico: bool = True  # True = manda dati automaticamente su Telegram
main_loop = None

CSV_HEADERS = ["timestamp", "temperatura_C", "umidita_aria_pct", "pressione_hPa", "gas_voc_kOhm", "umidita_suolo_raw", "umidita_suolo_pct", "bme_ok", "delay_min"]

# =============================================================================
# LOGGING
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("Muschio")

# =============================================================================
# CSV
# =============================================================================

def init_csv():
    if not os.path.exists(CSV_FILENAME):
        with open(CSV_FILENAME, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=CSV_HEADERS).writeheader()
        log.info(f"CSV creato: {CSV_FILENAME}")

def salva_csv(dati: dict, timestamp: str):
    row = {
        "timestamp":         timestamp,
        "temperatura_C":     dati.get("temperatura"),
        "umidita_aria_pct":  dati.get("umidita_aria"),
        "pressione_hPa":     dati.get("pressione"),
        "gas_voc_kOhm":      dati.get("gas_voc"),
        "umidita_suolo_raw": dati.get("umidita_suolo_raw"),
        "umidita_suolo_pct": dati.get("umidita_suolo_pct"),
        "bme_ok":            dati.get("bme_ok"),
        "delay_min":         dati.get("delay_min"),
    }
    with open(CSV_FILENAME, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=CSV_HEADERS).writerow(row)

# =============================================================================
# FORMATTAZIONE MESSAGGIO TELEGRAM
# =============================================================================

def formatta_dati(dati: dict, timestamp: str) -> str:
    """Costruisce il messaggio formattato da inviare su Telegram."""

    def v(key, decimali=1, unita=""):
        val = dati.get(key)
        if val is None:
            return "—"
        return f"{round(float(val), decimali)}{unita}"

    # Indicatore qualità aria VOC
    gas = dati.get("gas_voc", 0)
    if gas is None:
        qualita = "—"
    elif float(gas) > 100:
        qualita = "🟢 Buona"
    elif float(gas) > 50:
        qualita = "🟡 Discreta"
    else:
        qualita = "🔴 Scarsa"

    # Indicatore umidità suolo
    suolo = dati.get("umidita_suolo_pct", 0)
    if suolo is None:
        stato_suolo = "—"
    elif float(suolo) < 30:
        stato_suolo = "🏜️ Asciutto"
    elif float(suolo) < 70:
        stato_suolo = "✅ Ottimale"
    else:
        stato_suolo = "💧 Saturo"

    bme_warn = "" if dati.get("bme_ok", True) else "\n⚠️ BME680: errore lettura!"

    return (
        f"🌿 *Muschio Monitor*\n"
        f"📅 {timestamp}\n"
        f"─────────────────\n"
        f"🌡️ Temperatura:   *{v('temperatura', 1, ' °C')}*\n"
        f"💧 Umidità aria:  *{v('umidita_aria', 1, ' %')}*\n"
        f"🌬️ Pressione:     *{v('pressione', 1, ' hPa')}*\n"
        f"🧪 Gas VOC:       *{v('gas_voc', 1, ' kΩ')}* — {qualita}\n"
        f"🌱 Umidità suolo: *{v('umidita_suolo_pct', 1, ' %')}* — {stato_suolo}\n"
        f"⏱️ Intervallo:    *{dati.get('delay_min', '—')} min*"
        f"{bme_warn}"
    )

# =============================================================================
# MQTT — Callbacks
# =============================================================================

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        log.info("Connesso a HiveMQ Cloud!")
        client.subscribe(TOPIC_DATI)
        client.subscribe(TOPIC_STATUS)
        log.info(f"Subscribe su: {TOPIC_DATI}, {TOPIC_STATUS}")
    else:
        log.error(f"Connessione MQTT fallita (rc={rc})")

def on_disconnect(client, userdata, rc):
    if rc != 0:
        log.warning(f"Disconnessione inattesa (rc={rc}). Riconnessione automatica...")

def on_message(client, userdata, msg):
    """Chiamata ad ogni messaggio MQTT ricevuto."""
    global ultimi_dati

    topic   = msg.topic
    payload = msg.payload.decode("utf-8").strip()
    log.info(f"[MQTT] {topic}: {payload}")

    if topic == TOPIC_DATI:
        # Dati sensori dall'ESP32
        try:
            dati = json.loads(payload)
        except json.JSONDecodeError:
            log.error(f"JSON non valido: {payload}")
            return

        ultimi_dati = dati
        timestamp   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        salva_csv(dati, timestamp)

        # Invia i dati su Telegram a tutti i chat registrati
        testo = formatta_dati(dati, timestamp)
        if invio_automatico:
            invia_telegram_async(testo)

    elif topic == TOPIC_STATUS:
        # Messaggi di stato dall'ESP32 (conferme comandi, benvenuto, ecc.)
        invia_telegram_async(f"📡 ESP32: {payload}")

def invia_telegram_async(testo: str):
    """Invia un messaggio Telegram in modo asincrono dal thread MQTT."""
    if not chat_id_registrati:
        log.warning("Nessun chat_id registrato — fai /start sul bot prima!")
        return
    if telegram_app is None:
        return

    async def _invia():
        for cid in chat_id_registrati:
            try:
                await telegram_app.bot.send_message(
                    chat_id=cid,
                    text=testo,
                    parse_mode="Markdown"
                )
            except Exception as e:
                log.error(f"Errore invio Telegram a {cid}: {e}")

    import asyncio
    asyncio.run_coroutine_threadsafe(_invia(), main_loop)

# =============================================================================
# MQTT CLIENT — Setup
# =============================================================================

def avvia_mqtt() -> mqtt.Client:
    """Crea, configura e avvia il client MQTT in un thread separato."""
    client = mqtt.Client(client_id="PC_Muschio_Bot", clean_session=True)
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set()  # TLS con certificati di sistema (HiveMQ usa Let's Encrypt)
    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect
    client.on_message    = on_message

    try:
        client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    except Exception as e:
        log.error(f"Impossibile connettersi a HiveMQ: {e}")
        log.error("Verifica hostname, username e password nel file di configurazione.")
        raise SystemExit(1)

    # loop_start() avvia il network loop in un thread daemon separato
    client.loop_start()
    log.info(f"Client MQTT avviato (thread separato)")
    return client

# =============================================================================
# COMANDI TELEGRAM
# =============================================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    chat_id_registrati.add(cid)
    log.info(f"Nuovo utente registrato: {cid}")
    await update.message.reply_text(
        "🌿 *Muschio Monitor attivo!*\n\n"
        "Riceverai i dati ambientali del barattolo appena l'ESP32 li invia.\n\n"
        "Comandi disponibili:\n"
        "/stato — mostra gli ultimi dati ricevuti\n"
        "/delay N — cambia intervallo campionamento (es. /delay 30)\n"
        "/help — questa guida",
        parse_mode="Markdown"
    )

async def cmd_stato(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id_registrati.add(update.effective_chat.id)
    if not ultimi_dati:
        await update.message.reply_text(
            "⏳ Nessun dato ricevuto ancora.\n"
            "L'ESP32 invia dati ogni volta che si sveglia dal Deep Sleep."
        )
        return
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await update.message.reply_text(
        formatta_dati(ultimi_dati, timestamp),
        parse_mode="Markdown"
    )

async def cmd_delay(update: Update, context: ContextTypes.DEFAULT_TYPE, mqtt_client: mqtt.Client):
    chat_id_registrati.add(update.effective_chat.id)

    # Controlla che sia stato passato un argomento
    if not context.args or len(context.args) != 1:
        await update.message.reply_text(
            "❌ Uso corretto: `/delay N`\n"
            "Dove N è il numero di minuti (1–720).\n"
            "Esempio: `/delay 30`",
            parse_mode="Markdown"
        )
        return

    try:
        minuti = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Il valore deve essere un numero intero.")
        return

    if minuti < 1 or minuti > 720:
        await update.message.reply_text("❌ Il delay deve essere tra 1 e 720 minuti.")
        return

    # Pubblica il comando sul topic MQTT — l'ESP32 lo leggerà al prossimo risveglio
    comando = f"delay:{minuti}"
    mqtt_client.publish(TOPIC_COMANDO, comando)
    log.info(f"[Telegram] Comando inviato: {comando}")

    await update.message.reply_text(
        f"✅ Comando inviato: delay = *{minuti} minuti*\n\n"
        f"⚠️ L'ESP32 è in Deep Sleep — il nuovo delay sarà attivo "
        f"dal prossimo risveglio (entro {ultimi_dati.get('delay_min', '?')} min).",
        parse_mode="Markdown"
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌿 *Muschio Monitor — Guida comandi*\n\n"
        "/start — registra questa chat per ricevere i dati\n"
        "/stato — mostra gli ultimi dati ricevuti\n"
        "/auto_on  — attiva invio automatico dati\n"
        "/auto_off — disattiva invio automatico dati\n"
        "/delay N — imposta intervallo campionamento a N minuti\n"
        "(minimo 1, massimo 720)\n"
        "/help — mostra questa guida\n\n"
        "I dati vengono inviati automaticamente ad ogni campionamento dell'ESP32.",
    )

async def cmd_auto_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global invio_automatico
    invio_automatico = True
    chat_id_registrati.add(update.effective_chat.id)
    await update.message.reply_text("✅ Invio automatico *attivato*. Riceverai i dati ad ogni campionamento.", parse_mode="Markdown")

async def cmd_auto_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global invio_automatico
    invio_automatico = False
    chat_id_registrati.add(update.effective_chat.id)
    await update.message.reply_text("🔕 Invio automatico *disattivato*. Usa /stato per vedere i dati quando vuoi.", parse_mode="Markdown")

# =============================================================================
# MAIN
# =============================================================================

def main():
    import asyncio
    global main_loop
    main_loop = asyncio.get_event_loop()
    global telegram_app

    log.info("=" * 50)
    log.info("  TPI MUSCHIO — Bot Telegram + MQTT Bridge")
    log.info("=" * 50)

    init_csv()

    # Avvia MQTT in background
    mqtt_client = avvia_mqtt()

    # Costruisci l'app Telegram
    telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Registra i comandi
    telegram_app.add_handler(CommandHandler("start", cmd_start))
    telegram_app.add_handler(CommandHandler("stato", cmd_stato))
    telegram_app.add_handler(CommandHandler("help",  cmd_help))
    telegram_app.add_handler(CommandHandler("auto_on",  cmd_auto_on))
    telegram_app.add_handler(CommandHandler("auto_off", cmd_auto_off))

    # /delay ha bisogno del mqtt_client — usiamo una lambda
    telegram_app.add_handler(
        CommandHandler("delay",
            lambda u, c: cmd_delay(u, c, mqtt_client))
    )

    log.info("Bot Telegram avviato. Scrivi /start sul bot per iniziare.")
    log.info("Premi Ctrl+C per uscire.")

    # Avvia il polling Telegram (bloccante)
    telegram_app.run_polling(allowed_updates=Update.ALL_TYPES)

    # Pulizia
    mqtt_client.loop_stop()
    mqtt_client.disconnect()


if __name__ == "__main__":
    main()