# robot_control.py - Main entry point
#
# Threading model:
#   Core 0 (main): Serial comms loop via SerialComms.update()
#   Core 1:        PID + encoder control loop
#
# Shared state between cores lives inside the SerialComms instance:
#   comms.current_cmd   -> read by Core 1
#   comms.target_speed  -> read by Core 1
#   comms.v_left/right  -> written by Core 1

from machine import Pin
from encoder_portable import Encoder
from twowheel import TwoWheel
from PID import PID
from comms import SerialComms
import time
import _thread

# --- 1. HARDWARE SETUP ---
# NOTE: Motor 1 is physically wired in reverse - direction bool is always flipped.
# TODO: Fix by resoldering motor 1 wires when time permits.
robot = TwoWheel(motor1_pins=(6, 7), motor2_pins=(20, 19))
enc_left  = Encoder(Pin(2,  Pin.IN), Pin(3,  Pin.IN))
enc_right = Encoder(Pin(10, Pin.IN), Pin(11, Pin.IN))

pid_left  = PID(kp=150, ki=150, kd=0.1, output_limits=(0, 65535))
pid_right = PID(kp=150, ki=150, kd=0.1, output_limits=(0, 65535))

# --- 2. COMMS SETUP ---
comms = SerialComms(
    uart_id=1,
    tx_pin=4,
    rx_pin=5,
    baudrate=115200,
    timeout_ms=500,
    speed_hz=20,
    battery_hz=1,
    battery_adc_pin=26,
)

# --- 3. MOTOR WRITE HELPER ---
def apply_command(cmd, pwm_l, pwm_r):
    if cmd == "FORWARD":
        robot.motor1_write(pwm_l, False)  # inverted wiring
        robot.motor2_write(pwm_r, True)

    elif cmd == "BACKWARD":
        robot.motor1_write(pwm_l, True)   # inverted wiring
        robot.motor2_write(pwm_r, False)

    elif cmd == "LEFT":
        robot.motor1_write(pwm_l, True)   # inverted wiring
        robot.motor2_write(pwm_r, True)

    elif cmd == "RIGHT":
        robot.motor1_write(pwm_l, False)  # inverted wiring
        robot.motor2_write(pwm_r, False)

    else:  # STOP
        robot.motor1_write(0, True)
        robot.motor2_write(0, True)

# --- 4. CORE 1 - PID / ENCODER LOOP ---
def control_loop():
    print("[Core 1] Control loop started.")
    while True:
        cmd   = comms.current_cmd
        speed = comms.target_speed

        v_l = abs(enc_left.velocity())
        v_r = abs(enc_right.velocity())

        if cmd == "STOP":
            apply_command("STOP", 0, 0)
            pid_left.reset()
            pid_right.reset()
        else:
            pid_left.setpoint  = speed
            pid_right.setpoint = speed
            pwm_l = int(pid_left.update(v_l))
            pwm_r = int(pid_right.update(v_r))
            apply_command(cmd, pwm_l, pwm_r)

        # Push latest velocities back to comms for telemetry
        comms.update_velocities(v_l, v_r)

        time.sleep_ms(10)  # 100Hz control loop

# --- 5. START ---
print("[Core 0] Starting control thread on Core 1...")
_thread.start_new_thread(control_loop, ())

print("[Core 0] Comms loop running...")
while True:
    comms.update()
    time.sleep_ms(5)  # ~200Hz polling, comms handles its own send scheduling