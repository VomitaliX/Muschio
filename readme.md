# 🌿 TPI Muschio — Documentazione di Progetto

## Panoramica

Sistema di monitoraggio ambientale IoT per un ecosistema in barattolo (terrario di muschio). Un ESP32 legge i dati da sensori ambientali e di suolo, li pubblica via MQTT su HiveMQ Cloud, e un bot Telegram li riceve e permette il controllo remoto — funziona da qualsiasi rete, anche a scuola tramite hotspot del telefono.

---

## Struttura del progetto

```
tpi_muschio/
├── esp32_muschio.ino      ← Firmware ESP32 (Arduino IDE)
├── monitor_muschio.py     ← Bot Telegram + Bridge MQTT (PC)
├── grafico_muschio.py     ← Visualizzatore grafici matplotlib
├── log_muschio.csv        ← Generato automaticamente
└── preferenze.json        ← Generato automaticamente (stato auto/off)
```

---

## Architettura del sistema

```
ESP32 (hotspot telefono)
    │
    │  Wi-Fi → hotspot
    ▼
HiveMQ Cloud (broker MQTT gratuito, TLS porta 8883)
    │
    ├──► topic: progetto/muschio/dati    → dati sensori (JSON)
    ├──► topic: progetto/muschio/status  → messaggi di stato ESP32
    └──◄ topic: progetto/muschio/comando ← comandi dal bot (/delay N)
    │
    ▼
monitor_muschio.py (PC o laptop)
    ├── Bot Telegram → notifiche e comandi
    └── log_muschio.csv → storico dati
```

---

## 1. Hardware e cablaggio

### Componenti
| Componente | Descrizione |
|---|---|
| ESP32 (ESP-WROOM-32) | Microcontrollore principale |
| BME680 | Sensore aria: temperatura, umidità, pressione, VOC |
| Sensore capacitivo V1.2 (ocra) | Umidità del suolo |
| Power Bank USB | Alimentazione ESP32 |

### Schema di cablaggio

```
ESP32          BME680
─────          ──────
3.3V    ──→   VCC
GND     ──→   GND
GPIO21  ──→   SDA
GPIO22  ──→   SCL

ESP32          Sensore Capacitivo V1.2
─────          ──────────────────────
3.3V    ──→   VCC
GND     ──→   GND
GPIO34  ──→   AOUT
```

> ⚠️ Usare sempre il pin **3V3** — mai il 5V/VIN. GPIO34 è solo input, perfetto per l'ADC.

---

## 2. Setup HiveMQ Cloud (broker MQTT)

1. Vai su [hivemq.com/mqtt-cloud-broker](https://www.hivemq.com/mqtt-cloud-broker/) → crea account gratuito
2. Crea un nuovo cluster → annota l'**hostname** (es. `abc123.s1.eu.hivemq.cloud`)
3. Vai su **Access Management** → **Credentials** → crea username e password
4. Questi dati vanno inseriti sia nel firmware ESP32 che in `monitor_muschio.py`

---

## 3. Setup ESP32 (Arduino IDE)

### Librerie richieste
Installale dal Gestore Librerie (`Strumenti → Gestisci librerie`):
- `Adafruit BME680 Library` by Adafruit
- `Adafruit Unified Sensor` by Adafruit (dipendenza automatica)
- `PubSubClient` by Nick O'Leary

### Configurazione obbligatoria nel firmware

Apri `esp32_muschio.ino` e modifica queste costanti in cima al file:

```cpp
const char* WIFI_SSID     = "NOME_HOTSPOT";          // hotspot del telefono
const char* WIFI_PASSWORD = "PASSWORD_HOTSPOT";
const char* MQTT_HOST     = "abc123.s1.eu.hivemq.cloud"; // il tuo hostname
const char* MQTT_USER     = "TUO_USERNAME";
const char* MQTT_PASS     = "TUA_PASSWORD";
```

### Flash e Serial Monitor
1. Collega ESP32 via USB → seleziona scheda `ESP32 Dev Module`
2. Seleziona la porta COM corretta (`Strumenti → Porta`)
3. Clicca Upload (potrebbe servire tenere premuto BOOT durante il caricamento)
4. Apri Serial Monitor a **115200 baud** per vedere i log in tempo reale

---

## 4. Calibrazione sensore umidità suolo

Il sensore capacitivo V1.2 va calibrato una volta sola. I valori ADC **scendono** quando il suolo è bagnato (più capacitanza → tensione output minore).

**Procedura:**
1. Apri il Serial Monitor a 115200 baud
2. **Asciutto:** Tieni il sensore in aria → annota il valore `ADC raw` → assegna a `SOIL_DRY_VALUE`
3. **Bagnato:** Immergi il sensore in acqua → annota il valore `ADC raw` → assegna a `SOIL_WET_VALUE`
4. Ricarica il firmware

Valori tipici: Asciutto ~3200–3500 / Bagnato ~1200–1500

---

## 5. Setup Python (monitor_muschio.py)

### Prerequisiti
```bash
pip install paho-mqtt python-telegram-bot
```

### Configurazione
Apri `monitor_muschio.py` e modifica:

```python
TELEGRAM_TOKEN = "IL_TUO_TOKEN"              # da @BotFather su Telegram
MQTT_HOST      = "abc123.s1.eu.hivemq.cloud"
MQTT_USER      = "TUO_USERNAME"
MQTT_PASS      = "TUA_PASSWORD"
```

### Avvio
```bash
python monitor_muschio.py
```

---

## 6. Bot Telegram — Comandi disponibili

| Comando | Effetto |
|---|---|
| `/start` | Registra la chat, inizia a ricevere dati automaticamente |
| `/stato` | Mostra gli ultimi dati ricevuti dall'ESP32 |
| `/delay N` | Imposta intervallo campionamento a N minuti (1–720) |
| `/auto_on` | Attiva invio automatico dati ad ogni campionamento |
| `/auto_off` | Disattiva invio automatico (usa /stato per vedere i dati) |
| `/help` | Lista comandi |

> Il comando `/delay` viene salvato in **memoria RTC** dell'ESP32 — sopravvive ai Deep Sleep. Si azzera solo se togli l'alimentazione.

---

## 7. Formato dati MQTT

**Topic dati:** `progetto/muschio/dati`

```json
{
  "temperatura": 23.86,
  "umidita_aria": 90.74,
  "pressione": 996.63,
  "gas_voc": 50.12,
  "umidita_suolo_raw": 2100,
  "umidita_suolo_pct": 57.1,
  "bme_ok": true,
  "delay_min": 15
}
```

**Topic comando:** `progetto/muschio/comando` — formato: `delay:N`

**Topic status:** `progetto/muschio/status` — messaggi testuali di stato dall'ESP32

### Colonne CSV generate
| Campo | Unità | Note |
|---|---|---|
| timestamp | YYYY-MM-DD HH:MM:SS | Data e ora locale del PC |
| temperatura_C | °C | — |
| umidita_aria_pct | % | — |
| pressione_hPa | hPa | — |
| gas_voc_kOhm | kΩ | Valori alti = aria più pulita |
| umidita_suolo_raw | 0–4095 | ADC 12-bit grezzo |
| umidita_suolo_pct | % | 0 = asciutto, 100 = saturo |
| bme_ok | true/false | False = errore lettura sensore |
| delay_min | minuti | Intervallo campionamento attivo |

---

## 8. Visualizzatore grafici (grafico_muschio.py)

```bash
pip install matplotlib pandas

python grafico_muschio.py              # Storico completo
python grafico_muschio.py --ultime 24  # Solo ultime 24 ore
python grafico_muschio.py --live       # Aggiornamento automatico
python grafico_muschio.py --salva      # Salva come PNG
```

---

## 9. Flusso operativo ESP32

Ad ogni risveglio dal Deep Sleep:
1. Legge umidità suolo (ADC, media 10 campioni)
2. Inizializza BME680 e legge temperatura, umidità, pressione, VOC
3. Si connette al Wi-Fi (timeout 15s — protegge il Power Bank)
4. Si connette a HiveMQ Cloud TLS (timeout 10s)
5. Subscribe a `progetto/muschio/comando` e aspetta 3s eventuali comandi
6. Se arriva un comando `delay:N` → aggiorna il valore in memoria RTC
7. Pubblica JSON su `progetto/muschio/dati`
8. Entra in Deep Sleep per il numero di minuti configurato

---

## 10. Troubleshooting

| Sintomo | Causa probabile | Soluzione |
|---|---|---|
| ESP32 rc=-2 su MQTT | Credenziali HiveMQ errate | Vai su Access Management e ricrea le credenziali |
| ESP32 non si connette al Wi-Fi | SSID/password hotspot errati | Verifica le credenziali nel firmware |
| BME680 non trovato | Cablaggio I2C sbagliato | Controlla SDA=21, SCL=22; prova indirizzo 0x76 |
| Suolo sempre 0% o 100% | Calibrazione errata | Ricalibra con il Serial Monitor |
| Bot Python non riceve dati | Token Telegram errato o HiveMQ giù | Verifica token e credenziali HiveMQ |
| Power Bank si spegne | Timeout non scatta | Verifica `WIFI_TIMEOUT_MS` e `MQTT_TIMEOUT_MS` nel firmware |
| DeprecationWarning paho-mqtt | Versione API vecchia | Usa `mqtt.CallbackAPIVersion.VERSION2` nel costruttore |
