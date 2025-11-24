import os
import sys
import django
import paho.mqtt.client as mqtt
import time

# ==========================
# SETUP DJANGO di LAPTOP
# ==========================
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Parkwell.settings")
django.setup()

from main.models import RealTimeSpot


# ==========================
# TOPIK → SLOT
# ==========================
topic_to_spot = {
    "monitor/slot1": "Slot 1",
    "monitor/slot2": "Slot 2",
    "monitor/slot3": "Slot 3",
    "monitor/slot4": "Slot 4",
    "monitor/slot5": "Slot 5",
    "monitor/slot6": "Slot 6",
}


# ==========================
# CALLBACK MQTT
# ==========================
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ MQTT Terhubung ke Broker")
    else:
        print("❌ Gagal terhubung! kode:", rc)

    # Subscribe semua topik
    for topic in topic_to_spot:
        client.subscribe(topic)
        print(f"📡 Subscribe → {topic}")


def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload = msg.payload.decode().strip()
        distance = float(payload)
        slot_number = topic_to_spot.get(topic)

        print(f"\n📥 Data Masuk")
        print(f"📌 Topic: {topic}")
        print(f"📏 Jarak: {distance} cm")
        print(f"🚗 Slot   : {slot_number}")

        spot, created = RealTimeSpot.objects.get_or_create(spot_number=slot_number)

        # Update status slot
        spot.update_status_from_distance(distance)

        print(f"🔄 Status diperbarui: {spot.status}")
        print("=" * 50)

    except Exception as e:
        print(f"⚠️ ERROR memproses pesan dari {msg.topic}: {e}")


def on_disconnect(client, userdata, rc):
    print("⚠️ MQTT Terputus! Coba reconnect...")
    while True:
        try:
            client.reconnect()
            print("🔁 Reconnected!")
            break
        except:
            print("⏳ Reconnect gagal... mencoba lagi...")
            time.sleep(2)


# ==========================
# JALANKAN MQTT CLIENT
# ==========================
BROKER_IP = "192.168.1.13"   # IP Raspberry Pi kamu

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.on_disconnect = on_disconnect

print(f"🔌 Menghubungkan ke MQTT Broker {BROKER_IP} ...")
client.connect(BROKER_IP, 1883, 60)

# Loop selamanya
client.loop_forever()
