import paho.mqtt.client as mqtt
from gpiozero import DistanceSensor
import time
from datetime import datetime

# ==========================
# Konfigurasi MQTT DI RASPI
# ==========================
BROKER = "192.168.1.8"
PORT = 1883

TOPICS = {
    "monitor/slot1": {"echo": 6, "trigger": 5},
    "monitor/slot2": {"echo": 24, "trigger": 23},
    "monitor/slot3": {"echo": 27, "trigger": 17},
    "monitor/slot4": {"echo": 22, "trigger": 16},
}

MIN_DISTANCE_CHANGE = 1.0  # perbedaan minimal untuk publish


# ==========================
# MQTT Client
# ==========================
client = mqtt.Client()

def connect_mqtt():
    """Auto reconnect MQTT"""
    while True:
        try:
            client.connect(BROKER, PORT, 60)
            print("? MQTT Connected to broker")
            return
        except Exception as e:
            print(f"? MQTT Connection failed: {e}")
            print("? Retry in 2s...")
            time.sleep(2)

connect_mqtt()


# ==========================
# Inisialisasi Sensor
# ==========================
sensors = {}
last_distances = {}

for topic, pins in TOPICS.items():
    try:
        sensors[topic] = DistanceSensor(
            echo=pins["echo"],
            trigger=pins["trigger"],
            max_distance=2
        )
        last_distances[topic] = None
        print(f"?? Sensor OK ? {topic} (Trig={pins['trigger']}, Echo={pins['echo']})")
    except Exception as e:
        print(f"?? Gagal inisialisasi sensor {topic}: {e}")


# ==========================
# Fungsi Status
# ==========================
def deteksi_status(jarak):
    return "Terisi" if jarak < 10 else "Kosong"


# ==========================
# LOOP UTAMA
# ==========================
try:
    while True:
        waktu = datetime.now().strftime("%H:%M:%S")

        for topic, sensor in sensors.items():
            try:
                jarak = round(sensor.distance * 100, 2)
            except Exception as e:
                print(f"[{waktu}] ?? Error membaca sensor {topic}: {e}")
                continue

            status = deteksi_status(jarak)
            last = last_distances[topic]

            # Publish jika beda signifikan
            if last is None or abs(jarak - last) >= MIN_DISTANCE_CHANGE:
                try:
                    client.publish(topic, str(jarak))
                    print(f"[{waktu}] ?? {topic} ? {jarak:.2f} cm ({status})")
                    last_distances[topic] = jarak
                except Exception as e:
                    print(f"[{waktu}] ? Publish gagal: {e}")
                    connect_mqtt()

        time.sleep(1)

except KeyboardInterrupt:
    print("\n?? Program dihentikan.")
