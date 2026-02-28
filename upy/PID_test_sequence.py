from machine import Pin
from encoder_portable import Encoder
from twowheel import TwoWheel
from PID import PID
import time

# --- 1. HARDWARE AND PID SETUP ---
robot = TwoWheel(motor1_pins=(6, 7), motor2_pins=(20, 19))
enc_left = Encoder(Pin(2, Pin.IN), Pin(3, Pin.IN))
enc_right = Encoder(Pin(10, Pin.IN), Pin(11, Pin.IN))
pid_left = PID(kp=150, ki=150, kd=0.1, output_limits=(0, 65535))
pid_right = PID(kp=150, ki=150, kd=0.1, output_limits=(0, 65535))

# --- 2. TEST SEQUENCE ---
# Each step: (command, speed in pulses/sec, duration in ms)
TEST_SEQUENCE = [
    ("FORWARD",  2000, 2000),
    ("STOP",       0,  500),
    ("LEFT",     1500, 1000),
    ("STOP",       0,  500),
    ("FORWARD",  2000, 2000),
    ("STOP",       0,  500),
    ("RIGHT",    1500, 1000),
    ("STOP",       0,  500),
    ("BACKWARD", 2000, 2000),
    ("STOP",       0,  500),
]

# --- 3. MAIN LOOP ---
print("Starting test sequence...")

for (current_cmd, target_v, duration_ms) in TEST_SEQUENCE:
    print(f"CMD: {current_cmd} | Speed: {target_v} | Duration: {duration_ms}ms")
    pid_left.reset()
    pid_right.reset()

    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < duration_ms:

        # A. Read Encoder Velocities
        v_l = abs(enc_left.velocity())
        v_r = abs(enc_right.velocity())

        # B. Set PID Targets
        pid_left.setpoint = target_v
        pid_right.setpoint = target_v

        # C. Compute PID Outputs
        pwm_left = int(pid_left.update(v_l))
        pwm_right = int(pid_right.update(v_r))

        # D. Print Encoder Readings
        print(f"ENC L: {v_l:.1f} | ENC R: {v_r:.1f} pulses/sec")

        # E. Apply Motor Commands
        # NOTE: Motor 1 is physically wired in reverse - direction bool is always flipped.
        # TODO: Fix by resoldering motor 1 wires when time permits.
        if current_cmd == "FORWARD":
            robot.motor1_write(pwm_left, False)   # False = forward (inverted wiring)
            robot.motor2_write(pwm_right, True)

        elif current_cmd == "BACKWARD":
            robot.motor1_write(pwm_left, True)    # True = backward (inverted wiring)
            robot.motor2_write(pwm_right, False)

        elif current_cmd == "LEFT":
            robot.motor1_write(pwm_left, True)    # inverted
            robot.motor2_write(pwm_right, True)

        elif current_cmd == "RIGHT":
            robot.motor1_write(pwm_left, False)   # inverted
            robot.motor2_write(pwm_right, False)

        else:  # STOP
            robot.motor1_write(0, True)
            robot.motor2_write(0, True)

        time.sleep_ms(10)

# --- 4. DONE - STOP MOTORS ---
robot.motor1_write(0, True)
robot.motor2_write(0, True)
print("Test sequence complete.")