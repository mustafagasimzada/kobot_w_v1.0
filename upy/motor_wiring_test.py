from machine import Pin
from twowheel import TwoWheel
import time

robot = TwoWheel(motor1_pins=(6, 7), motor2_pins=(20, 19))

TESTS = [
    ("Motor 1 - direction True",  1, True),
    ("Motor 1 - direction False", 1, False),
    ("Motor 2 - direction True",  2, True),
    ("Motor 2 - direction False", 2, False),
]

PWM = 30000  # ~45% power, safe for a quick test

for (label, motor, direction) in TESTS:
    print(f"TEST: {label}")
    if motor == 1:
        robot.motor1_write(PWM, direction)
        robot.motor2_write(0, True)
    else:
        robot.motor1_write(0, True)
        robot.motor2_write(PWM, direction)
    time.sleep_ms(1500)
    robot.motor1_write(0, True)
    robot.motor2_write(0, True)
    print("  -> Which direction did it spin? Note it down.")
    time.sleep_ms(1000)

print("Done. Use your observations to map directions correctly.")