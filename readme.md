# TPI Muschio — Guida di Setup Completa

## Struttura del progetto

```
tpi_muschio/
├── esp32_muschio.ino      ← Firmware ESP32 (Arduino IDE)
├── monitor_muschio.py     ← Script Python (PC)
└── log_muschio.csv        ← Generato automaticamente dallo script Python
```

---

## 1. Setup Broker MQTT (Mosquitto sul PC)

### Installazione

**Windows:**
Scarica da https://mosquitto.org/download/ e installa. Poi:
```
mosquitto -v
```

**Ubuntu/Debian:**
```bash
sudo apt install mosquitto mosquitto-clients
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
```

**macOS:**
```bash
brew install mosquitto
brew services start mosquitto
```

### Verifica che funzioni
```bash
# Terminale 1 — Subscriber di test
mosquitto_sub -h localhost -t test/prova

# Terminale 2 — Pubblica messaggio di test
mosquitto_pub -h localhost -t test/prova -m "ciao muschio"
```
Se il terminale 1 stampa "ciao muschio" → Mosquitto funziona.

### Trova il tuo IP locale (da inserire nel firmware ESP32)
```bash
# Linux/macOS
ip addr show   # o: hostname -I

# Windows
ipconfig
```
Cerca un indirizzo tipo `192.168.1.X` nella tua rete locale.

---

## 2. Setup Python

```bash
pip install paho-mqtt
```

**Avvio:**
```bash
python3 monitor_muschio.py
```

---

## 3. Setup ESP32 (Arduino IDE)

### Librerie richieste (Gestore Librerie Arduino)
- `Adafruit BME680 Library` by Adafruit
- `Adafruit Unified Sensor` by Adafruit (dipendenza)
- `PubSubClient` by Nick O'Leary

### Scheda e porta
- Board: `ESP32 Dev Module` (o il tuo modello specifico)
- Upload Speed: `115200`
- Porta: la COM/tty assegnata all'ESP32

### Modifiche obbligatorie nel firmware prima del flash
1. `WIFI_SSID` → Nome della tua rete Wi-Fi
2. `WIFI_PASSWORD` → Password Wi-Fi
3. `MQTT_SERVER` → IP del tuo PC (es. `"192.168.1.100"`)

---

## 4. Calibrazione Sensore Umidità Suolo

Il sensore capacitivo V1.2 va calibrato una volta sola.

**Procedura:**
1. Carica il firmware con `Serial.begin(115200)` e apri il Serial Monitor
2. **Asciutto:** Tieni il sensore in aria → annota il valore `ADC raw`  
   → Assegna a `SOIL_DRY_VALUE` nel firmware
3. **Bagnato:** Immergi il sensore in acqua → annota il valore `ADC raw`  
   → Assegna a `SOIL_WET_VALUE` nel firmware
4. Ricarica il firmware con i valori corretti

**Perché il valore scende quando è bagnato?**  
Il sensore capacitivo misura la capacitanza del suolo. L'acqua aumenta la costante dielettrica → maggiore capacitanza → il circuito RC interno produce una tensione di output più bassa → ADC più basso.

---

## 5. Schema di Cablaggio

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

> ⚠️ GPIO34 è solo input — non ha resistore pull-up interno. Perfetto per l'ADC.

---

## 6. Formato Dati MQTT

**Topic:** `progetto/muschio/dati`

**Payload JSON esempio:**
```json
{
  "temperatura": 22.45,
  "umidita_aria": 78.30,
  "pressione": 1013.25,
  "gas_voc": 145.32,
  "umidita_suolo_raw": 2100,
  "umidita_suolo_pct": 57.1,
  "bme_ok": true
}
```

**Colonne CSV generate:**
| Campo | Unità |
|---|---|
| timestamp | YYYY-MM-DD HH:MM:SS |
| temperatura_C | °C |
| umidita_aria_pct | % |
| pressione_hPa | hPa |
| gas_voc_kOhm | kΩ (valori alti = aria più pulita) |
| umidita_suolo_raw | 0–4095 (ADC 12-bit) |
| umidita_suolo_pct | % (0 = asciutto, 100 = saturo) |
| bme_ok | true/false |

---

## 7. Troubleshooting

| Sintomo | Causa probabile | Soluzione |
|---|---|---|
| ESP32 non si connette al Wi-Fi | SSID/password errati | Verifica le credenziali |
| ESP32 non si connette al broker | IP sbagliato o firewall | Verifica IP e `mosquitto -v` |
| BME680 non trovato | Cablaggio I2C sbagliato | Controlla SDA=21, SCL=22; prova indirizzo 0x76 |
| Suolo sempre 0% o 100% | Calibrazione errata | Ricalibra con Serial Monitor |
| Script Python non riceve dati | Mosquitto non avviato | Avvia Mosquitto prima dello script |
| Power Bank si spegne | Loop infinito senza sleep | Verifica i timeout Wi-Fi/MQTT nel firmware |