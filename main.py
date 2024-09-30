import time
import network
import ubinascii
import machine
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

# Клас для збору температури
class TemperatureSensor:
    def __init__(self, pin_number):
        self.ds_pin = Pin(pin_number)
        self.ds_sensor = DS18X20(OneWire(self.ds_pin))
        self.smoothed_temperature = None

    def read_temperature(self):
        """Зчитує температуру з датчика"""
        roms = self.ds_sensor.scan()
        if not roms:
            return None
        self.ds_sensor.convert_temp()
        time.sleep(1)  # Очікуємо для отримання точних даних
        return self.ds_sensor.read_temp(roms[0])

    def moving_average_filter(self, new_value):
        """Застосовує фільтр ковзного середнього для згладжування"""
        if self.smoothed_temperature is None:
            # Ініціалізуємо перше значення, якщо воно ще не було встановлено
            self.smoothed_temperature = new_value
        else:
            # Застосовуємо згладжування
            self.smoothed_temperature = 0.9 * self.smoothed_temperature + 0.1 * new_value
        return self.smoothed_temperature

# Клас для обробки MQTT-з'єднання
class MQTTClientHandler:
    def __init__(self, client_id, broker, topic, user, password):
        self.client_id = client_id
        self.broker = broker
        self.topic = topic
        self.user = user
        self.password = password
        self.client = None

    def connect(self):
        """Підключення до MQTT-брокера з обробкою помилок"""
        connected = False
        while not connected:
            try:
                if self.client is None:
                    self.client = MQTTClient(self.client_id, self.broker, user=self.user, password=self.password)
                self.client.connect()
                print("Connected to MQTT broker")
                connected = True
            except Exception as e:
                print("Failed to connect to MQTT broker:", e)
                print("Retrying in 5 seconds...")
                self.client = None  # Перезапускаємо клієнт перед повторною спробою
                time.sleep(5)

    def publish(self, message):
        """Публікація даних до MQTT"""
        try:
            self.client.publish(self.topic, message)
            print("Published message:", message)
        except Exception as e:
            print("Failed to publish message:", e)
            print("Reconnecting to MQTT broker...")
            self.connect()

    def disconnect(self):
        """Відключення від MQTT-брокера"""
        if self.client:
            try:
                self.client.disconnect()
                print("Disconnected from MQTT broker")
            except Exception as e:
                print("Failed to disconnect from MQTT broker:", e)

# Клас для управління Wi-Fi з'єднанням
class WiFiManager:
    def __init__(self, ssid, password):
        self.ssid = ssid
        self.password = password
        self.wlan = network.WLAN(network.STA_IF)

    def connect(self):
        """Підключення до Wi-Fi"""
        self.wlan.active(True)
        self.wlan.connect(self.ssid, self.password)
        print('Connecting to Wi-Fi...')

    def is_connected(self):
        """Перевірка чи підключені до Wi-Fi"""
        return self.wlan.isconnected()

    def check_and_reconnect(self):
        """Перевіряємо з'єднання і перепідключаємось, якщо його немає"""
        if not self.is_connected():
            print('Wi-Fi connection lost. Reconnecting...')
            self.connect()

# Основна програма
def main():
    wifi_manager = WiFiManager(SSID, PASSWORD)
    wifi_manager.connect()

    temp_sensor = TemperatureSensor(pin_number=16)
    mqtt_handler = MQTTClientHandler(CLIENT_ID, MQTT_BROKER, MQTT_TOPIC, MQTT_USER, MQTT_PASSWORD)

    mqtt_handler.connect()

    last_wifi_check = time.time()

    try:
        while True:
            current_time = time.time()

            # Перевіряємо з'єднання з Wi-Fi кожні 10 секунд
            if current_time - last_wifi_check >= 10:
                wifi_manager.check_and_reconnect()
                last_wifi_check = current_time

            # Продовжуємо збирати дані і публікувати їх незалежно від Wi-Fi
            raw_temperature = temp_sensor.read_temperature()
            if raw_temperature is not None:
                smoothed_temperature = temp_sensor.moving_average_filter(raw_temperature)
                print("Raw Temperature:", raw_temperature)
                print("Smoothed Temperature:", round(smoothed_temperature, 2))

                # Якщо Wi-Fi є, намагаємось передати дані через MQTT
                if wifi_manager.is_connected():
                    mqtt_handler.publish(str(round(smoothed_temperature, 2)))
                else:
                    print("Wi-Fi not connected. Cannot publish data.")
                    
            time.sleep(1)

    except KeyboardInterrupt:
        mqtt_handler.disconnect()
        print("Program terminated")

# Виклик основної програми
main()
