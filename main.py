import time
import network
import ubinascii
import machine
from machine import Pin, I2C
from onewire import OneWire
from ds18x20 import DS18X20
from umqtt.simple import MQTTClient
from ssd1306 import SSD1306_I2C

# Налаштування Wi-Fi
SSID = "aonline"
PASSWORD = "1qaz2wsx3edc"

# Налаштування MQTT
MQTT_BROKER = "greenhouse.net.ua"
MQTT_TOPIC = "aparts/temp_out"
MQTT_ERROR_TOPIC = "aparts/error/temp_out"
MQTT_USER = "mqtt"
MQTT_PASSWORD = "qwerty"
CLIENT_ID = ubinascii.hexlify(machine.unique_id())

# Клас для роботи з OLED-дисплеєм
class OLEDDisplay:
    def __init__(self, width, height, scl_pin, sda_pin):
        """Ініціалізує OLED дисплей з вказаними параметрами"""
        i2c = I2C(0, scl=Pin(scl_pin), sda=Pin(sda_pin))  # Додайте ID шини, наприклад, 1
        self.oled = SSD1306_I2C(width, height, i2c)
        self.clear()

    def clear(self):
        """Очищує екран"""
        self.oled.fill(0)
        self.oled.show()

    def display_text(self, text, x=0, y=0):
        """Відображає текст на OLED дисплеї на вказаних координатах"""
        self.oled.text(text, x, y)
        self.oled.show()

    def display_temperature(self, temperature):
        """Виводить температуру на дисплей у форматі 'Температура: X C'"""
        self.clear()
        self.display_text("Температура:", 0, 0)
        self.display_text(f"{temperature} C", 0, 20)

# Клас для роботи з температурним сенсором
class TemperatureSensor:
    def __init__(self, pin_number):
        self.ds_pin = Pin(pin_number)
        self.ds_sensor = DS18X20(OneWire(self.ds_pin))
        self.smoothed_temperature = None

    def read_temperature(self):
        """Зчитує температуру з сенсора, якщо він доступний"""
        roms = self.ds_sensor.scan()
        if not roms:
            return None  # Сенсор не знайдено
        self.ds_sensor.convert_temp()
        time.sleep(1)  # Очікування точного зчитування
        return self.ds_sensor.read_temp(roms[0])

    def moving_average_filter(self, new_value):
        """Застосовує згладжування значень температури"""
        if self.smoothed_temperature is None:
            self.smoothed_temperature = new_value
        else:
            self.smoothed_temperature = 0.9 * self.smoothed_temperature + 0.1 * new_value
        return self.smoothed_temperature

# Клас для роботи з MQTT
class MQTTClientHandler:
    def __init__(self, client_id, broker, topic, user, password):
        self.client_id = client_id
        self.broker = broker
        self.topic = topic
        self.user = user
        self.password = password
        self.client = None

    def connect(self):
        """Підключення до MQTT брокера з обробкою помилок"""
        connected = False
        while not connected:
            try:
                if self.client is None:
                    self.client = MQTTClient(self.client_id, self.broker, user=self.user, password=self.password)
                self.client.connect()
                print("Підключено до MQTT брокера")
                connected = True
            except Exception as e:
                print("Не вдалося підключитися до MQTT брокера:", e)
                print("Повтор через 5 секунд...")
                self.client = None  # Скидання клієнта перед повтором
                time.sleep(5)

    def publish(self, message, topic=None):
        """Публікація даних до MQTT з опційним параметром теми"""
        try:
            topic_to_use = topic if topic else self.topic
            self.client.publish(topic_to_use, message)
            print("Опубліковано повідомлення:", message)
        except Exception as e:
            print("Не вдалося опублікувати повідомлення:", e)
            print("Повторне підключення до MQTT брокера...")
            self.connect()

    def disconnect(self):
        """Відключення від MQTT брокера"""
        if self.client:
            try:
                self.client.disconnect()
                print("Відключено від MQTT брокера")
            except Exception as e:
                print("Не вдалося відключитися від MQTT брокера:", e)

# Клас для управління Wi-Fi з'єднанням
class WiFiManager:
    def __init__(self, ssid, password):
        self.ssid = ssid
        self.password = password
        self.wlan = network.WLAN(network.STA_IF)

    def connect(self):
        """Підключення до Wi-Fi"""
        self.wlan.active(True)
        print('Підключення до Wi-Fi...')
        self.wlan.connect(self.ssid, self.password)
        while not self.is_connected():
            print("Очікування підключення до Wi-Fi...")
            time.sleep(1)
        print("Підключено до Wi-Fi")

    def is_connected(self):
        """Перевірка підключення до Wi-Fi"""
        return self.wlan.isconnected()

    def check_and_reconnect(self):
        """Перевірка з'єднання та перепідключення у разі розриву"""
        if not self.is_connected():
            print('Втрачено з’єднання з Wi-Fi. Перепідключення...')
            self.connect()

# Основна програма
def main():
    wifi_manager = WiFiManager(SSID, PASSWORD)
    wifi_manager.connect()

    temp_sensor = TemperatureSensor(pin_number=16)
    mqtt_handler = MQTTClientHandler(CLIENT_ID, MQTT_BROKER, MQTT_TOPIC, MQTT_USER, MQTT_PASSWORD)
    mqtt_handler.connect()

    oled_display = None  # Ініціалізація змінної для OLED-дисплея
    oled_available = True  # Змінна для позначення наявності OLED

    # Спроба ініціалізації OLED-дисплея
    try:
        oled_display = OLEDDisplay(128, 64, scl_pin=5, sda_pin=4)  # Ініціалізація OLED
    except Exception as e:
        print("OLED-дисплей не виявлено або виникла помилка:", e)
        oled_available = False  # Позначаємо, що OLED недоступний

    last_wifi_check = time.time()

    try:
        while True:
            current_time = time.time()

            if current_time - last_wifi_check >= 10:
                wifi_manager.check_and_reconnect()
                last_wifi_check = current_time

            print("Зчитування даних температури...")
            raw_temperature = temp_sensor.read_temperature()
            if raw_temperature is not None:
                smoothed_temperature = temp_sensor.moving_average_filter(raw_temperature)
                rounded_temp = round(smoothed_temperature, 2)
                print("Згладжена температура:", rounded_temp)

                # Виведення температури на OLED, якщо він доступний
                if oled_available:
                    oled_display.display_temperature(rounded_temp)

                # Публікація даних у MQTT, якщо Wi-Fi підключено
                if wifi_manager.is_connected():
                    print("Публікація даних температури...")
                    mqtt_handler.publish(str(rounded_temp))
                else:
                    print("Wi-Fi не підключено. Неможливо опублікувати дані.")
            else:
                print("Помилка сенсора: Неможливо зчитати температуру")
                mqtt_handler.publish("sensor error", topic=MQTT_ERROR_TOPIC)

            time.sleep(1)

    except KeyboardInterrupt:
        mqtt_handler.disconnect()
        print("Програма завершена")

# Запуск основної програми
main()
