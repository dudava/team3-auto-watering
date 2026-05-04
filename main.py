from machine import Pin, ADC, I2C
import time

# ========== НАСТРОЙКИ ==========
PIN_ZONE1 = 14
PIN_ZONE2 = 15
PIN_PUMP   = 16
PIN_BUTTON = 17
PIN_POT1   = 26
PIN_POT2   = 27
LED_BUILTIN = 25          # встроенный светодиод для индикации работы

DRY_THRESHOLD   = 30
WET_THRESHOLD   = 70
MAX_PUMP_TIME   = 3
MIN_INTERVAL    = 0       # временно отключаем защиту от частого полива (для теста)
MANUAL_TIMEOUT  = 10

# Расписание (отключим для чистоты теста, оставим пустым)
SCHEDULE = []   # [(8,0,30,1)]  – можно раскомментировать позже

# ========== ИНИЦИАЛИЗАЦИЯ ПЕРИФЕРИИ ==========
zone1 = Pin(PIN_ZONE1, Pin.OUT, value=0)
zone2 = Pin(PIN_ZONE2, Pin.OUT, value=0)
pump  = Pin(PIN_PUMP,   Pin.OUT, value=0)
button = Pin(PIN_BUTTON, Pin.IN, Pin.PULL_UP)
led_builtin = Pin(LED_BUILTIN, Pin.OUT)

adc1 = ADC(PIN_POT1)
adc2 = ADC(PIN_POT2)

# ---------- OLED (с защитой от ошибок) ----------
oled_ok = False
try:
    import ssd1306
    i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)
    oled = ssd1306.SSD1306_I2C(128, 64, i2c)
    oled_ok = True
    print("OLED инициализирован")
except Exception as e:
    print("OLED не подключён:", e)

# ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
last_water_time = 0
manual_mode_active = False
block_reason = "OK"

LOG_SIZE = 5
log_buffer = []

def log(msg):
    timestamp = time.time()
    print("[{:.1f}] {}".format(timestamp, msg))
    log_buffer.append((timestamp, msg))
    if len(log_buffer) > LOG_SIZE:
        log_buffer.pop(0)

# ========== ФУНКЦИИ ==========
def read_moisture(zone):
    if zone == 1:
        val = adc1.read_u16() >> 8
    else:
        val = adc2.read_u16() >> 8
    moisture = int(val / 255 * 100)
    return max(0, min(100, moisture))

def set_watering(zone_num, enable):
    if enable:
        if zone_num == 1:
            zone1.value(1)
        else:
            zone2.value(1)
        pump.value(1)
        log(f"Зона {zone_num} ВКЛ")
    else:
        if zone_num == 1:
            zone1.value(0)
        else:
            zone2.value(0)
        if zone1.value() == 0 and zone2.value() == 0:
            pump.value(0)
        log(f"Зона {zone_num} ВЫКЛ")

def can_water():
    global block_reason
    now = time.time()
    if manual_mode_active:
        block_reason = "РУЧНОЙ"
        return False
    if now - last_water_time < MIN_INTERVAL and last_water_time != 0:
        block_reason = f"ЗАЩИТА {MIN_INTERVAL - (now-last_water_time):.0f}с"
        return False
    block_reason = "OK"
    return True

def auto_water_by_moisture():
    if not can_water():
        return
    global last_water_time
    m1 = read_moisture(1)
    m2 = read_moisture(2)
    log(f"Влажность: {m1}% / {m2}%")
    watered = False
    if m1 < DRY_THRESHOLD:
        set_watering(1, True)
        start = time.time()
        while time.time() - start < MAX_PUMP_TIME:
            if read_moisture(1) >= WET_THRESHOLD:
                break
            time.sleep(1)
        set_watering(1, False)
        watered = True
    if m2 < DRY_THRESHOLD:
        set_watering(2, True)
        start = time.time()
        while time.time() - start < MAX_PUMP_TIME:
            if read_moisture(2) >= WET_THRESHOLD:
                break
            time.sleep(1)
        set_watering(2, False)
        watered = True
    if watered:
        last_water_time = time.time()
        log("Автополив завершён")

def manual_water():
    global manual_mode_active, last_water_time
    if not can_water():
        log("Ручной отклонён: " + block_reason)
        return
    manual_mode_active = True
    log("Ручной полив (обе зоны)")
    zone1.value(1)
    zone2.value(1)
    pump.value(1)
    start = time.time()
    while time.time() - start < MANUAL_TIMEOUT:
        if button.value() == 0:
            break
        time.sleep(0.1)
    zone1.value(0)
    zone2.value(0)
    pump.value(0)
    manual_mode_active = False
    last_water_time = time.time()
    log("Ручной выключен")

def update_oled():
    if not oled_ok:
        return
    oled.fill(0)
    m1 = read_moisture(1)
    m2 = read_moisture(2)
    oled.text(f"Вл: {m1}%  {m2}%", 0, 0)
    oled.text(f"З1:{zone1.value()} З2:{zone2.value()} H:{pump.value()}", 0, 10)
    oled.text(block_reason[:16], 0, 20)
    oled.text(f"След: нет", 0, 30)   # упростим
    if log_buffer:
        oled.text(log_buffer[-1][1][:16], 0, 40)
    if len(log_buffer) >= 2:
        oled.text(log_buffer[-2][1][:16], 0, 50)
    oled.show()

# ========== ОСНОВНОЙ ЦИКЛ ==========
log("Система запущена")
last_auto = 0
last_oled = 0
last_blink = 0
blink_state = 0

while True:
    now = time.time()
    
    # Мигаем встроенным светодиодом (каждые 0.5 сек) – признак жизни
    if now - last_blink > 0.5:
        blink_state = 1 - blink_state
        led_builtin.value(blink_state)
        last_blink = now
    
    # Кнопка
    if button.value() == 0 and not manual_mode_active:
        time.sleep_ms(50)
        if button.value() == 0:
            manual_water()
            while button.value() == 0:
                time.sleep_ms(10)
    
    # Автополив по влажности – каждые 3 секунды
    if now - last_auto >= 3:
        auto_water_by_moisture()
        last_auto = now
    
    # OLED обновление – не чаще 2 раз в секунду
    if now - last_oled >= 0.5:
        update_oled()
        last_oled = now
    
    time.sleep(0.1)