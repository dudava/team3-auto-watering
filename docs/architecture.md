## Симуляция
- Raspberry Pi Pico MicroPython в Wokwi. 
## Компоненты
- Potentiometer ×2 (ADC), Relay module (или LED) ×3, кнопки, OLED SSD1306 (опционально), RTC (опционально). 
## Описание схемы (итоговой)
- Potentiometer: SIG→ADC (Pico GP26/27), питание 3.3V/GND.
- Реле/LED: IN→GPIO (2 зоны + насос).
- Кнопка: GPIO pull-up, нажатие на GND.
- OLED/RTC: I2C на общих SDA/SCL.
