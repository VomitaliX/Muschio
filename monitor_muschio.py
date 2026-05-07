#!/usr/bin/env python3
"""
=============================================================================
TPI MUSCHIO — Script Python di monitoraggio MQTT
=============================================================================
Funzionalità:
  - Subscribe al topic MQTT 'progetto/muschio/dati'
  - Parsing del JSON ricevuto dall'ESP32
  - Stampa a video con formattazione leggibile
  - Salvataggio in file CSV con timestamp
  - Riconnessione automatica al broker se la connessione cade

Prerequisiti:
  pip install paho-mqtt

Uso:
  python3 monitor_muschio.py

Configurazione: modifica le costanti nella sezione CONFIG più sotto.
=============================================================================
"""

import json
import csv
import time
import logging
import os
from datetime import datetime

import paho.mqtt.client as mqtt

# =============================================================================
# CONFIG — Modifica questi valori
# =============================================================================
BROKER_HOST  = "localhost"          # IP/hostname del broker Mosquitto
BROKER_PORT  = 1883                 # Porta MQTT standard
MQTT_TOPIC   = "progetto/muschio/dati"
CSV_FILENAME = "log_muschio.csv"    # File di log CSV (creato nella stessa cartella)

# Intervallo di riconnessione in secondi (usato dal loop principale)
RECONNECT_DELAY = 10  # secondi tra un tentativo di riconnessione e l'altro

# =============================================================================
# LOGGING — Output a video con timestamp
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("Muschio")

# =============================================================================
# INTESTAZIONI CSV
# =============================================================================
CSV_HEADERS = [
    "timestamp",
    "temperatura_C",
    "umidita_aria_pct",
    "pressione_hPa",
    "gas_voc_kOhm",
    "umidita_suolo_raw",
    "umidita_suolo_pct",
    "bme_ok"
]


# =============================================================================
# GESTIONE CSV
# =============================================================================

def init_csv(filepath: str) -> None:
    """
    Crea il file CSV con intestazioni se non esiste già.
    Se esiste, non sovrascrive i dati presenti.
    """
    if not os.path.exists(filepath):
        with open(filepath, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writeheader()
        log.info(f"File CSV creato: {filepath}")
    else:
        log.info(f"File CSV esistente trovato: {filepath} — aggiunta in coda.")


def append_to_csv(filepath: str, row: dict) -> None:
    """
    Aggiunge una riga di dati al file CSV.
    """
    with open(filepath, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writerow(row)


# =============================================================================
# CALLBACK MQTT
# =============================================================================

def on_connect(client, userdata, flags, rc):
    """
    Callback chiamata quando il client si connette (o riconnette) al broker.
    rc=0 significa successo. Valori >0 indicano errori.
    """
    rc_messages = {
        0: "Connessione riuscita",
        1: "Versione protocollo non accettata",
        2: "Identificatore client non valido",
        3: "Server non disponibile",
        4: "Username/password errati",
        5: "Non autorizzato",
    }
    msg = rc_messages.get(rc, f"Errore sconosciuto (rc={rc})")

    if rc == 0:
        log.info(f"✅ Connesso al broker MQTT — {msg}")
        # Il subscribe va fatto QUI, dentro on_connect,
        # così viene ripristinato automaticamente dopo ogni riconnessione.
        client.subscribe(MQTT_TOPIC)
        log.info(f"📡 In ascolto sul topic: '{MQTT_TOPIC}'")
    else:
        log.error(f"❌ Connessione fallita — {msg}")


def on_disconnect(client, userdata, rc):
    """
    Callback chiamata quando il client si disconnette dal broker.
    rc=0 = disconnessione pulita (richiesta dal client).
    rc≠0 = disconnessione inattesa (rete caduta, broker spento, ecc.).
    La riconnessione automatica è gestita da loop_forever() con reconnect_delay.
    """
    if rc == 0:
        log.info("🔌 Disconnesso dal broker (chiusura pulita).")
    else:
        log.warning(f"⚠️  Disconnessione inattesa (rc={rc}). Riconnessione in corso...")


def on_message(client, userdata, msg):
    """
    Callback chiamata ad ogni messaggio ricevuto sul topic sottoscritto.
    Effettua il parsing del JSON, stampa a video e salva nel CSV.
    """
    log.info("─" * 60)
    log.info(f"📨 Messaggio ricevuto su '{msg.topic}'")

    # --- Parsing JSON ---
    try:
        payload_str = msg.payload.decode("utf-8")
        data = json.loads(payload_str)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        log.error(f"Errore nel parsing del messaggio: {e}")
        log.error(f"Payload grezzo: {msg.payload}")
        return

    # --- Timestamp locale ---
    now = datetime.now()
    timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")

    # --- Estrazione dati con valori di default se chiave mancante ---
    temperatura      = data.get("temperatura",         None)
    umidita_aria     = data.get("umidita_aria",        None)
    pressione        = data.get("pressione",           None)
    gas_voc          = data.get("gas_voc",             None)
    suolo_raw        = data.get("umidita_suolo_raw",   None)
    suolo_pct        = data.get("umidita_suolo_pct",   None)
    bme_ok           = data.get("bme_ok",              None)

    # --- Stampa formattata a video ---
    print()
    print(f"  🕐 {timestamp_str}")
    print(f"  🌡️  Temperatura aria:    {_fmt(temperatura, '°C')}")
    print(f"  💧 Umidità aria:        {_fmt(umidita_aria, '%')}")
    print(f"  🌬️  Pressione:           {_fmt(pressione, 'hPa')}")
    print(f"  🧪 Gas VOC:             {_fmt(gas_voc, 'kΩ')}")
    print(f"  🌱 Umidità suolo:       {_fmt(suolo_pct, '%')}  (raw: {suolo_raw})")
    print(f"  📡 BME680 OK:           {bme_ok}")
    print()

    # Avviso se il BME680 ha segnalato un errore
    if bme_ok is False:
        log.warning("⚠️  Il BME680 ha segnalato un errore di lettura in questo ciclo!")

    # --- Salvataggio CSV ---
    row = {
        "timestamp":          timestamp_str,
        "temperatura_C":      temperatura,
        "umidita_aria_pct":   umidita_aria,
        "pressione_hPa":      pressione,
        "gas_voc_kOhm":       gas_voc,
        "umidita_suolo_raw":  suolo_raw,
        "umidita_suolo_pct":  suolo_pct,
        "bme_ok":             bme_ok,
    }
    try:
        append_to_csv(userdata["csv_path"], row)
        log.info(f"💾 Riga salvata in '{userdata['csv_path']}'")
    except IOError as e:
        log.error(f"Errore nella scrittura CSV: {e}")


def _fmt(value, unit: str) -> str:
    """Helper: formatta un valore numerico con unità, o '—' se None."""
    if value is None:
        return "— (dato mancante)"
    return f"{value} {unit}"


# =============================================================================
# MAIN
# =============================================================================

def main():
    log.info("=" * 60)
    log.info("  TPI MUSCHIO — Monitor MQTT avviato")
    log.info("=" * 60)

    # Inizializza il file CSV
    init_csv(CSV_FILENAME)

    # Crea il client MQTT
    # clean_session=True: il broker non conserva messaggi persi durante le disconnessioni
    client = mqtt.Client(
        client_id="PC_Muschio_Monitor",
        clean_session=True,
        userdata={"csv_path": CSV_FILENAME}  # Passa il path CSV alle callback
    )

    # Assegna le callback
    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect
    client.on_message    = on_message

    # Connessione al broker con riconnessione automatica
    log.info(f"🔌 Connessione a {BROKER_HOST}:{BROKER_PORT}...")

    try:
        client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    except ConnectionRefusedError:
        log.error(f"❌ Connessione rifiutata! Mosquitto è in ascolto su {BROKER_HOST}:{BROKER_PORT}?")
        log.error("   Avvia Mosquitto con: mosquitto -v  (o verifica che sia avviato come servizio)")
        raise SystemExit(1)
    except OSError as e:
        log.error(f"❌ Errore di rete: {e}")
        raise SystemExit(1)

    # loop_forever() gestisce automaticamente:
    #  - Il loop di rete (receive/send)
    #  - La riconnessione automatica in caso di disconnessione inattesa
    #  - Il keepalive MQTT (ping al broker ogni 60 secondi)
    # Premi Ctrl+C per uscire.
    log.info("▶️  Loop MQTT avviato. Premi Ctrl+C per uscire.")
    try:
        client.loop_forever(retry_first_connection=True)
    except KeyboardInterrupt:
        log.info("\n⏹️  Interruzione richiesta dall'utente. Chiusura...")
        client.disconnect()
        log.info("✅ Disconnesso. Arrivederci!")


if __name__ == "__main__":
    main()
