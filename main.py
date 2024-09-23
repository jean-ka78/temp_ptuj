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
    while not wlan.isconnected():
        print('Connecting to network...')
        time.sleep(1)
    print('Connected to Wi-Fi:', wlan.ifconfig())

# Функція зчитування температури
def read_temperature():
    roms = ds_sensor.scan()
    ds_sensor.convert_temp()
    time.sleep(1)
    for rom in roms:
        temp = ds_sensor.read_temp(rom)
        smoothedValue = 0.9 * smoothedValue + 0.1 * temp
        return round(smoothedValue, 2)  # Округлення до двох знаків після коми

# Фільтр ковзного середнього для згладжування показників температури
def moving_average_filter(new_value, values, window_size):
    values.append(new_value)
    if len(values) > window_size:
        values.pop(0)
    return round(sum(values) / len(values),2)

# Основна програма
def main():
    connect_wifi()
    
    client = MQTTClient(CLIENT_ID, MQTT_BROKER, user=MQTT_USER, password=MQTT_PASSWORD)
    client.connect()
    
    temperature_values = []
    window_size = 10  # Розмір вікна для фільтрації

    try:
        while True:
            raw_temperature = read_temperature()
            smoothed_temperature = moving_average_filter(raw_temperature, temperature_values, window_size)
            print("Raw Temperature:", raw_temperature)
            print("Smoothed Temperature:", smoothed_temperature)
            client.publish(MQTT_TOPIC, str(smoothed_temperature))
            time.sleep(1)
    except KeyboardInterrupt:
        client.disconnect()
        print("Program terminated")

# Виклик основної програми
main()
