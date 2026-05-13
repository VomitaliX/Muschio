// =============================================================================
// TPI MUSCHIO - Firmware ESP32 v2.0
// Broker: HiveMQ Cloud (MQTT over TLS)
// Controllo remoto: Bot Telegram via topic MQTT
// =============================================================================
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <Adafruit_BME680.h>

const char* WIFI_SSID      = "Fitter Happier";
const char* WIFI_PASSWORD  = "More productive";
const char* MQTT_HOST      = "69f128f236014b8689ffec3406c3f58d.s1.eu.hivemq.cloud";
const int   MQTT_PORT      = 8883;
const char* MQTT_USER      = "Muschio";
const char* MQTT_PASS      = "Muschio32";
const char* MQTT_CLIENT_ID = "Esp32_Muschio";
const char* TOPIC_DATI     = "progetto/muschio/dati";
const char* TOPIC_COMANDO  = "progetto/muschio/comando";
const char* TOPIC_STATUS   = "progetto/muschio/status";

const unsigned long WIFI_TIMEOUT_MS  = 15000;
const unsigned long MQTT_TIMEOUT_MS  = 10000;
const unsigned long COMANDO_WAIT_MS  = 3000;
const int DEFAULT_DELAY_MIN          = 1;
const int DELAY_MIN_CONSENTITO       = 1;
const int DELAY_MAX_CONSENTITO       = 720;

const int SOIL_DRY_VALUE = 3300;
const int SOIL_WET_VALUE = 1400;
const int SOIL_PIN       = 34;

// Memoria RTC: sopravvive al Deep Sleep, si azzera solo con reset/power off
RTC_DATA_ATTR int  rtcDelayMinuti = DEFAULT_DELAY_MIN;
RTC_DATA_ATTR bool rtcPrimoAvvio  = true;

// Certificato root CA HiveMQ (ISRG Root X1 - Let's Encrypt, scade 2035)
static const char* HIVEMQ_ROOT_CA = R"EOF(
-----BEGIN CERTIFICATE-----
MIIFazCCA1OgAwIBAgIRAIIQz7DSQONZRGPgu2OCiwAwDQYJKoZIhvcNAQELBQAw
TzELMAkGA1UEBhMCVVMxKTAnBgNVBAoTIEludGVybmV0IFNlY3VyaXR5IFJlc2Vh
cmNoIEdyb3VwMRUwEwYDVQQDEwxJU1JHIFJvb3QgWDEwHhcNMTUwNjA0MTEwNDM4
WhcNMzUwNjA0MTEwNDM4WjBPMQswCQYDVQQGEwJVUzEpMCcGA1UEChMgSW50ZXJu
ZXQgU2VjdXJpdHkgUmVzZWFyY2ggR3JvdXAxFTATBgNVBAMTDElTUkcgUm9vdCBY
MTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAK3oJHP0FDfzm54rVygc
h77ct984kIxuPOZXoHj3dcKi/vVqbvYATyjb3miGbESTtrFj/RQSa78f0uoxmyF+
0TM8ukj13Xnfs7j/EvEhmkvBioZxaUpmZmyPfjxwv60pIgbz5MDmgK7iS4+3mX6U
A5/TR5d8mUgjU+g4rk8Kb4Mu0UlXjIB0ttov0DiNewNwIRt18jA8+o+u3dpjq+sW
T8KOEUt+zwvo/7V3LvSye0rgTBIlDHCNAymg4VMk7BPZ7hm/ELNKjD+Jo2FR3qyH
B5T0Y3HsLuJvW5iB4YlcNHlsdu87kGJ55tukmi8mxdAQ4Q7e2RCOFvu396j3x+UC
B5iPNgiV5+I3lg02dZ77DnKxHZu8A/lJBdiB3QW0KtZB6awBdpUKD9jf1b0SHzUv
KBds0pjBqAlkd25HN7rOrFleaJ1/ctaJxQZBKT5ZPt0m9STJEadao0xAH0ahmbWn
OlFuhjuefXKnEgV4We0+UXgVCwOPjdAvBbI+e0ocS3MFEvzG6uBQE3xDk3SzynTn
jh8BCNAw1FtxNrQHusEwMFxIt4I7mKZ9YIqioymCzLq9gwQbooMDQaHWBfEbwrbw
qHyGO0aoSCqI3Haadr8faqU9GY/rOPNk3sgrDQoo//fb4hVC1CLQJ13hef4Y53CI
rU7m2Ys6xt0nUW7/vGT1M0NPAgMBAAGjQjBAMA4GA1UdDwEB/wQEAwIBBjAPBgNV
HRMBAf8EBTADAQH/MB0GA1UdDgQWBBR5tFnme7bl5AFzgAiIyBpY9umbbjANBgkq
hkiG9w0BAQsFAAOCAgEAVR9YqbyyqFDQDLHYGmkgJykIrGF1XIpu+ILlaS/V9lZL
ubhzEFnTIZd+50xx+7LSYK05qAvqFyFWhfFQDlnrzuBZ6brJFe+GnY+EgPbk6ZGQ
3BebYhtF8GaV0nxvwuo77x/Py9auJ/GpsMiu/X1+mvoiBOv/2X/qkSsisRcOj/KK
NFtY2PwByVS5uCbMiogziUwthDyC3+6WVwW6LLv3xLfHTjuCvjHIInNzktHCgKQ5
ORAzI4JMPJ+GslWYHb4phowim57iaztXOoJwTdwJx4nLCgdNbOhdjsnvzqvHu7Ur
TkXWStAmzOVyyghqpZXjFaH3pO3JLF+l+/+sKAIuvtd7u+Nxe5AW0wdeRlN8NwF
XQeFNNSe5AQScrphOiVhQ0RXroMk3q8GqNapQ/LIkI3SACLvMqUGeFxn3vYERB4r
SHSbQP1sLkpqSBRKABzL3IRSB6H1PJ9MR1+t97g7x0HEFznHufkZq2CirTMX0VF6
glJZwEJkPTMkjaHGE22oMicEMmUDaB4z3cGqFh3KOECD0Cki+4RbFU3kXGbOBiTv
4XZLkxN6TKRcN7G8VNSa+VGr5FGKF+U2a1xkqhVzWRJVkFhkKZKHsJfmBSvWkfU
TPBIFN+dG0JMdT/hsf9cWGrHMGEMLhNlZqv+XOGN1iNNk8aBJpDZDBQ=
-----END CERTIFICATE-----
)EOF";

WiFiClientSecure  wifiClient;
PubSubClient      mqttClient(wifiClient);
Adafruit_BME680   bme;

volatile bool nuovoComandoRicevuto = false;
volatile int  nuovoDelayRicevuto   = 0;

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String msg = "";
  for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];
  msg.trim();
  Serial.printf("[MQTT] Comando: '%s'\n", msg.c_str());

  if (msg.startsWith("delay:")) {
    int nd = msg.substring(6).toInt();
    if (nd >= DELAY_MIN_CONSENTITO && nd <= DELAY_MAX_CONSENTITO) {
      nuovoDelayRicevuto = nd;
      nuovoComandoRicevuto = true;
    } else {
      String err = "Errore: delay deve essere tra " +
                   String(DELAY_MIN_CONSENTITO) + " e " +
                   String(DELAY_MAX_CONSENTITO) + " minuti.";
      mqttClient.publish(TOPIC_STATUS, err.c_str());
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.printf("\n=== TPI Muschio v2.0 | Delay: %d min ===\n", rtcDelayMinuti);

  int   soilRaw     = readSoilMoisture();
  float soilPercent = mapSoilToPercent(soilRaw);
  float temp=0, hum=0, pres=0, gas=0;
  bool  bmeOK = initBME680();
  if (bmeOK) readBME680(temp, hum, pres, gas);

  if (!connectWiFi()) { enterDeepSleep(); return; }

  wifiClient.setCACert(HIVEMQ_ROOT_CA);
  mqttClient.setServer(MQTT_HOST, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);
  mqttClient.setBufferSize(512);

  if (!connectMQTT()) { enterDeepSleep(); return; }

  // Subscribe e aspetta comandi in arrivo
  mqttClient.subscribe(TOPIC_COMANDO);
  Serial.printf("[MQTT] Ascolto comandi per %dms...\n", COMANDO_WAIT_MS);
  unsigned long ws = millis();
  while (millis() - ws < COMANDO_WAIT_MS) {
    mqttClient.loop();
    delay(50);
  }

  // Aggiorna delay se è arrivato un comando da Telegram
  if (nuovoComandoRicevuto) {
    rtcDelayMinuti = nuovoDelayRicevuto;
    String ok = "Delay aggiornato a " + String(rtcDelayMinuti) +
                " minuti. Prossimo campionamento tra " +
                String(rtcDelayMinuti) + " min.";
    mqttClient.publish(TOPIC_STATUS, ok.c_str());
    delay(200);
    Serial.printf("[RTC] Nuovo delay salvato: %d min\n", rtcDelayMinuti);
  }

  if (rtcPrimoAvvio) {
    rtcPrimoAvvio = false;
    String benvenuto = "Muschio Monitor online! Delay: " +
                       String(rtcDelayMinuti) +
                       " min. Usa /delay N per cambiarlo.";
    mqttClient.publish(TOPIC_STATUS, benvenuto.c_str());
    delay(200);
  }

  publishData(temp, hum, pres, gas, soilRaw, soilPercent, bmeOK);
  delay(500);
  mqttClient.loop();
  enterDeepSleep();
}

void loop() {}

int readSoilMoisture() {
  long sum = 0;
  for (int i = 0; i < 10; i++) { sum += analogRead(SOIL_PIN); delay(10); }
  int raw = sum / 10;
  Serial.printf("[Suolo] ADC raw: %d\n", raw);
  return raw;
}

float mapSoilToPercent(int rawValue) {
  return constrain((float)map(rawValue, SOIL_DRY_VALUE, SOIL_WET_VALUE, 0, 100), 0.0f, 100.0f);
}

bool initBME680() {
  if (!bme.begin(0x77)) return false;
  bme.setTemperatureOversampling(BME680_OS_8X);
  bme.setHumidityOversampling(BME680_OS_2X);
  bme.setPressureOversampling(BME680_OS_4X);
  bme.setIIRFilterSize(BME680_FILTER_SIZE_3);
  bme.setGasHeater(320, 150);
  return true;
}

void readBME680(float &temp, float &hum, float &pres, float &gas) {
  if (!bme.performReading()) return;
  temp = bme.temperature;
  hum  = bme.humidity;
  pres = bme.pressure / 100.0F;
  gas  = bme.gas_resistance / 1000.0F;
  Serial.printf("[BME680] T:%.2f H:%.2f P:%.2f G:%.2f\n", temp, hum, pres, gas);
}

bool connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long t = millis();
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - t > WIFI_TIMEOUT_MS) return false;
    delay(500); Serial.print(".");
  }
  Serial.printf("\n[WiFi] Connesso: %s\n", WiFi.localIP().toString().c_str());
  return true;
}

bool connectMQTT() {
  unsigned long t = millis();
  while (!mqttClient.connected()) {
    if (millis() - t > MQTT_TIMEOUT_MS) return false;
    wifiClient.setInsecure(); // bypass verifica certificato (solo per test)
    if (mqttClient.connect(MQTT_CLIENT_ID, MQTT_USER, MQTT_PASS)) {
      Serial.println("[MQTT] Connesso a HiveMQ Cloud!");
    } else {
    Serial.print("[MQTT] Fallito, rc=");
    Serial.print(mqttClient.state()); // Questo ci dirà il CODICE errore
      delay(2000);
    }
  }
  return true;
}

void publishData(float temp, float hum, float pres, float gas,
                 int soilRaw, float soilPct, bool bmeOK) {
  char json[300];
  snprintf(json, sizeof(json),
    "{\"temperatura\":%.2f,\"umidita_aria\":%.2f,\"pressione\":%.2f,"
    "\"gas_voc\":%.2f,\"umidita_suolo_raw\":%d,\"umidita_suolo_pct\":%.1f,"
    "\"bme_ok\":%s,\"delay_min\":%d}",
    temp, hum, pres, gas, soilRaw, soilPct,
    bmeOK ? "true" : "false", rtcDelayMinuti);
  mqttClient.publish(TOPIC_DATI, json);
  Serial.printf("[MQTT] Pubblicato: %s\n", json);
}

void enterDeepSleep() {
  Serial.printf("[Sleep] Deep Sleep per %d minuti.\n", rtcDelayMinuti);
  Serial.flush();
  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);
  esp_sleep_enable_timer_wakeup((uint64_t)rtcDelayMinuti * 60ULL * 1000000ULL);
  esp_deep_sleep_start();
}
