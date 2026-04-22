from machine import Pin, ADC
import time

# ========== НАСТРОЙКИ ==========
PIN_ZONE1 = 14
PIN_ZONE2 = 15
PIN_PUMP = 16
PIN_BUTTON = 17
PIN_POT1 = 26
PIN_POT2 = 27

DRY_THRESHOLD = 30       # % влажности, ниже которой включаем полив
WET_THRESHOLD = 70       # % влажности, при которой выключаем
MAX_PUMP_TIME = 3       # макс. длительность полива (сек)
MIN_INTERVAL = 6       # мин. интервал между поливами (сек) = 10 минут
MANUAL_TIMEOUT = 30      # ручной полив длится 30 сек

# Расписание: (час, минута, длительность_сек, зона)
SCHEDULE = [
    (8, 0, 30, 1),
    (18, 0, 30, 2),
]

# ========== ИНИЦИАЛИЗАЦИЯ ==========
zone1 = Pin(PIN_ZONE1, Pin.OUT, value=0)
zone2 = Pin(PIN_ZONE2, Pin.OUT, value=0)
pump = Pin(PIN_PUMP, Pin.OUT, value=0)
button = Pin(PIN_BUTTON, Pin.IN, Pin.PULL_UP)

adc1 = ADC(PIN_POT1)
adc2 = ADC(PIN_POT2)

# ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
last_water_time = 0          # время последнего полива (сек с запуска)
manual_mode_active = False

def log(msg):
    print("[{:.1f}] {}".format(time.time(), msg))

# ========== ФУНКЦИИ ==========
def read_moisture(zone):
    """возвращает влажность в % (0-100)"""
    if zone == 1:
        val = adc1.read_u16() >> 8   # 0-65535 -> 0-255
        return int(val / 255 * 100)
    else:
        val = adc2.read_u16() >> 8
        return int(val / 255 * 100)

def set_watering(zone_num, enable):
    if enable:
        if zone_num == 1:
            zone1.value(1)
        else:
            zone2.value(1)
        pump.value(1)
        log(f"Зона {zone_num} полив ВКЛ")
    else:
        if zone_num == 1:
            zone1.value(0)
        else:
            zone2.value(0)
        if zone1.value() == 0 and zone2.value() == 0:
            pump.value(0)
        log(f"Зона {zone_num} полив ВЫКЛ")

def auto_water_by_moisture():
    global last_water_time
    now = time.time()
    if now - last_water_time < MIN_INTERVAL:
        return   # защита от частого полива

    m1 = read_moisture(1)
    m2 = read_moisture(2)
    log(f"Влажность: зона1={m1}% зона2={m2}%")
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
        log("Автополив по влажности завершён")

def check_schedule():
    now = time.localtime()
    hour = now[3]
    minute = now[4]
    for h, m, dur, zone in SCHEDULE:
        if h == hour and m == minute:
            return (zone, dur)
    return None

def manual_water():
    global manual_mode_active, last_water_time
    now = time.time()
    if now - last_water_time < MIN_INTERVAL and last_water_time != 0:
        log("Ручной полив отклонён: слишком часто")
        return
    if manual_mode_active:
        return
    manual_mode_active = True
    log("Ручной полив включён (обе зоны)")
    zone1.value(1)
    zone2.value(1)
    pump.value(1)
    start = time.time()
    while time.time() - start < MANUAL_TIMEOUT:
        if button.value() == 0:   # повторное нажатие -> досрочное выключение
            break
        time.sleep(0.1)
    zone1.value(0)
    zone2.value(0)
    pump.value(0)
    manual_mode_active = False
    last_water_time = time.time()
    log("Ручной полив выключен")

# ========== ОСНОВНОЙ ЦИКЛ ==========
log("Система автополива запущена (спринт 1)")
last_schedule_check = 0
last_auto_check = 0

while True:
    now = time.time()

    # Кнопка (ручной режим)
    if button.value() == 0 and not manual_mode_active:
        time.sleep_ms(50)
        if button.value() == 0:
            manual_water()
            while button.value() == 0:
                time.sleep_ms(10)

    # Расписание (раз в секунду)
    if now - last_schedule_check >= 1:
        sched = check_schedule()
        if sched and not manual_mode_active:
            zone, duration = sched
            if now - last_water_time >= MIN_INTERVAL:
                log(f"Полив по расписанию: зона {zone} на {duration} сек")
                set_watering(zone, True)
                time.sleep(duration)
                set_watering(zone, False)
                last_water_time = time.time()
            else:
                log("Расписание пропущено: слишком часто")
        last_schedule_check = now

    # Автополив по влажности (раз в 5 секунд)
    if now - last_auto_check >= 5:
        if not manual_mode_active:
            auto_water_by_moisture()
        last_auto_check = now

    time.sleep(0.1)