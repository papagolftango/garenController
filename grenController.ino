// ESP32 + 2-relay board (GPIO16/17). Active-LOW relays.
// Minimal BLE: 1 byte bitmask controls both relays.
// Bit0 = Relay1 (GPIO16), Bit1 = Relay2 (GPIO17). 1=ON.
// Auto-off: fixed 15 minutes per relay.

#include <Arduino.h>
#include <NimBLEDevice.h>   // Install "NimBLE-Arduino" from Library Manager

// ===== Pins & behaviour =====
static const int RELAY1_PIN = 16;
static const int RELAY2_PIN = 17;
static const bool RELAY_ACTIVE_LOW = true;   // keep true for this board

// ===== Auto-off (fixed) =====
static const uint32_t AUTO_OFF_MS = 15UL * 60UL * 1000UL;

// ===== BLE UUIDs (random) =====
#define SVC_UUID   "7e6b2f20-5f7a-4d7c-8c2a-5d9e2b1a0000"
#define RELAY_UUID "7e6b2f20-5f7a-4d7c-8c2a-5d9e2b1a0001"

// ===== State =====
static uint8_t relayBits = 0;           // bit0 -> R1, bit1 -> R2
static uint32_t offAtMsR1 = 0;
static uint32_t offAtMsR2 = 0;

NimBLECharacteristic* chRelay = nullptr;

inline void setRelayPin(int pin, bool on) {
  const int lvl = on ? (RELAY_ACTIVE_LOW ? LOW : HIGH)
                     : (RELAY_ACTIVE_LOW ? HIGH : LOW);
  digitalWrite(pin, lvl);
}

void applyOutputs() {
  setRelayPin(RELAY1_PIN, relayBits & 0x01);
  setRelayPin(RELAY2_PIN, relayBits & 0x02);
}

void armTimers(uint8_t bits) {
  const uint32_t now = millis();
  if (bits & 0x01) offAtMsR1 = now + AUTO_OFF_MS;
  if (bits & 0x02) offAtMsR2 = now + AUTO_OFF_MS;
}

// BLE write handler: 1 byte mask
class RelayCallbacks : public NimBLECharacteristicCallbacks {
  void onWrite(NimBLECharacteristic* c) override {
    std::string v = c->getValue();
    if (v.size() < 1) return;
    uint8_t newBits = (uint8_t)v[0] & 0x03;

    // If any bit transitions to ON, (re)arm its timer
    if ((newBits & 0x01) && !(relayBits & 0x01)) offAtMsR1 = millis() + AUTO_OFF_MS;
    if ((newBits & 0x02) && !(relayBits & 0x02)) offAtMsR2 = millis() + AUTO_OFF_MS;

    relayBits = newBits;
    applyOutputs();
    c->setValue(&relayBits, 1);
    c->notify();
  }
};

void setup() {
  pinMode(RELAY1_PIN, OUTPUT);
  pinMode(RELAY2_PIN, OUTPUT);
  relayBits = 0; applyOutputs();

  NimBLEDevice::init("ESP32 Garden");
  NimBLEServer* server = NimBLEDevice::createServer();
  NimBLEService* svc = server->createService(SVC_UUID);

  chRelay = svc->createCharacteristic(
      RELAY_UUID,
      NIMBLE_PROPERTY::READ | NIMBLE_PROPERTY::WRITE | NIMBLE_PROPERTY::NOTIFY);
  chRelay->setCallbacks(new RelayCallbacks());
  chRelay->setValue(&relayBits, 1);

  svc->start();
  NimBLEAdvertising* adv = NimBLEDevice::getAdvertising();
  adv->addServiceUUID(SVC_UUID);
  adv->setScanResponse(true);
  NimBLEDevice::startAdvertising();
}

void loop() {
  uint8_t newBits = relayBits;
  const uint32_t now = millis();

  // millis-safe expiry checks
  if ((relayBits & 0x01) && (int32_t)(now - offAtMsR1) >= 0) newBits &= ~0x01;
  if ((relayBits & 0x02) && (int32_t)(now - offAtMsR2) >= 0) newBits &= ~0x02;

  if (newBits != relayBits) {
    relayBits = newBits;
    applyOutputs();
    if (chRelay) { chRelay->setValue(&relayBits, 1); chRelay->notify(); }
  }

  delay(10);
}
