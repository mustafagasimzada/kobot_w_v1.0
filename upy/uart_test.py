from machine import UART, Pin
import time

uart = UART(1, baudrate=9600, tx=Pin(4), rx=Pin(5))

while True:
    uart.write(b'PICO_ALIVE\n')
    time.sleep_ms(500)