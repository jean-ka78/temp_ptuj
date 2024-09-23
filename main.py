import time
import network
import ubinascii
from machine import Pin
from onewire import OneWire
from ds18x20 import DS18X20
from umqtt.simple import MQTTClient

# Налаштування Wi-Fi
SSID = "A1"
PASSWORD = "1qaz2wsx3edc"

# Налаштування MQTT
MQTT_BROKER = "greenhouse.net.ua"
MQTT_TOPIC = "aparts/temp_out"
MQTT_USER = "mqtt"
MQTT_PASSWORD = "qwerty"
CLIENT_ID = ubinascii.hexlify(machine.unique_id())

# Налаштування GPIO для DS18B20
ds_pin = Pin(16)
ds_sensor = DS18X20(OneWire(ds_pin))

# Функція підключення до Wi-Fi
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    print('Connecting to Wi-Fi...')
    while not wlan.isconnected():
        time.sleep(1)
    print('Connected to Wi-Fi:', wlan.ifconfig())

# Функція перевірки з'єднання Wi-Fi і перепідключення при втраті
def check_wifi_connection():
    wlan = network.WLAN(network.STA_IF)
    if not wlan.isconnected():
        print('Wi-Fi connection lost. Reconnecting...')
        connect_wifi()

# Функція зчитування температури
def read_temperature():
    roms = ds_sensor.scan()
    ds_sensor.convert_temp()
    time.sleep(1)
    if roms:
        return ds_sensor.read_temp(roms[0])  # Повертаємо температуру з першого датчика

# Фільтр ковзного середнього для згладжування показників температури
def moving_average_filter(new_value, smoothed_value):
    return 0.9 * smoothed_value + 0.1 * new_value

# Основна програма
def main():
    connect_wifi()

    client = MQTTClient(CLIENT_ID, MQTT_BROKER, user=MQTT_USER, password=MQTT_PASSWORD)
    try:
        client.connect()
    except Exception as e:
        print('Failed to connect to MQTT broker:', e)
        return

    try:
        # Ініціалізація першим виміряним значенням температури
        initial_temperature = read_temperature()
        if initial_temperature is None:
            print("No sensors found.")
            return
        
        smoothed_temperature = initial_temperature  # Використовуємо перше значення для згладження

        while True:
            check_wifi_connection()  # Перевіряємо з'єднання з Wi-Fi

            raw_temperature = read_temperature()
            if raw_temperature is not None:
                smoothed_temperature = moving_average_filter(raw_temperature, smoothed_temperature)
                print("Raw Temperature:", raw_temperature)
                print("Smoothed Temperature:", round(smoothed_temperature, 2))

                try:
                    client.publish(MQTT_TOPIC, str(round(smoothed_temperature, 2)))
                except Exception as e:
                    print('MQTT publish failed, reconnecting to MQTT broker:', e)
                    try:
                        client.connect()  # Перепідключаємо MQTT-клієнт
                    except Exception as e:
                        print('Failed to reconnect to MQTT broker:', e)

            time.sleep(1)

    except KeyboardInterrupt:
        client.disconnect()
        print("Program terminated")

# Виклик основної програми
main()
