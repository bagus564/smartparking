import os
import sys
import django
import paho.mqtt.client as mqtt

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Parkwell.settings")
django.setup()

from main.models import Spot

topic_to_spot = {
    "parkir/slot1": "1",
    "parkir/slot2": "2",
    "parkir/slot3": "3",
    "parkir/slot4": "4",
}

def on_connect(client, userdata, flags, rc):
    print("Terhubung ke MQTT dengan kode:", rc)
    if rc == 0:
        print("MQTT Connected OK")
        for topic in topic_to_spot.keys():
            print("Subscribe:", topic)
            client.subscribe(topic)
    else:
        print("Gagal Connect MQTT")

def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload = msg.payload.decode()

        distance = float(payload)
        spot_number = topic_to_spot.get(topic)

        if spot_number is None:
            print("Topik tidak dikenali:", topic)
            return

        print(f"[MQTT] {topic} = {distance} cm")

        spot = Spot.objects.get(spot_number=spot_number)
        spot.update_status_from_distance(distance)

        print(f"Slot {spot_number} → {spot.status}")
        print("-"*40)

    except Exception as e:
        print("Error MQTT:", e)

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

BROKER = "192.168.1.13"   # ubah bila perlu

print("Mencoba konek ke broker:", BROKER)
client.connect(BROKER, 1883, 60)

client.loop_forever()
