# comms.py - Pico Serial Communication Module
# Handles all UART framing, parsing, telemetry scheduling, and failsafe logic.
# Runs on Core 0. Control loop runs on Core 1.
#
# Message Format (Pico → RPi):
#   Speed telemetry (20Hz):   "S:{left_vel:.2f}:{right_vel:.2f}\n"
#   Battery telemetry (1Hz):  "B:{voltage:.2f}\n"
#   Ack/error:                "E:{msg}\n"
#
# Message Format (RPi → Pico):
#   Command:  "C:{CMD}:{speed}\n"
#   Example:  "C:FORWARD:200.0\n"
#             "C:STOP:0.0\n"

from machine import UART, Pin, ADC
import utime

# --- Valid commands ---
VALID_COMMANDS = {"FORWARD", "BACKWARD", "LEFT", "RIGHT", "STOP"}


class SerialComms:
    def __init__(
        self,
        uart_id=0,
        tx_pin=0,
        rx_pin=1,
        baudrate=115200,
        timeout_ms=500,
        speed_hz=20,
        battery_hz=1,
        battery_adc_pin=26,
    ):
        self.uart = UART(uart_id, baudrate=baudrate, tx=Pin(tx_pin), rx=Pin(rx_pin))
        self._buf = ""

        # Failsafe
        self.timeout_ms = timeout_ms
        self._last_packet_time = utime.ticks_ms()
        self.timed_out = False

        # Shared command state (written by comms, read by control loop)
        self.current_cmd = "STOP"
        self.target_speed = 0.0

        # Telemetry scheduling
        self._speed_interval_ms = 1000 // speed_hz       # 50ms  @ 20Hz
        self._battery_interval_ms = 1000 // battery_hz   # 1000ms @ 1Hz
        self._last_speed_send = utime.ticks_ms()
        self._last_battery_send = utime.ticks_ms()

        # Toggles — disable individual telemetry streams if needed
        self.send_speed_enabled = True
        self.send_battery_enabled = True

        # Battery ADC
        self._adc = ADC(Pin(battery_adc_pin))

        # Latest telemetry values (written by control loop, read by comms)
        self.v_left = 0.0
        self.v_right = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self):
        """Call this in a loop on Core 0. Handles RX parsing and TX scheduling."""
        self._receive()
        self._check_failsafe()
        self._send_telemetry()

    def update_velocities(self, v_left, v_right):
        """Called by control loop (Core 1) to push latest encoder readings."""
        self.v_left = v_left
        self.v_right = v_right

    # ------------------------------------------------------------------
    # Receive
    # ------------------------------------------------------------------

    def _receive(self):
        try:
            if self.uart.any():
                raw = self.uart.read(64)
                self._buf += raw.decode("utf-8", "ignore") if raw else ""
                self._process_buffer()
        except Exception:
            self._buf = ""  # clear corrupt buffer and keep going

    def _process_buffer(self):
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            line = line.strip()
            if line:
                self._parse(line)

    def _parse(self, line):
        """Parse a single incoming frame."""
        try:
            parts = line.split(":")
            if parts[0] != "C" or len(parts) != 3:
                self._send_error("BAD_FRAME")
                return

            cmd = parts[1].upper()
            speed = float(parts[2])

            if cmd not in VALID_COMMANDS:
                self._send_error("BAD_CMD")
                return

            if speed < 0:
                self._send_error("BAD_SPEED")
                return

            # Valid packet — update state and reset failsafe timer
            self.current_cmd = cmd
            self.target_speed = speed
            self._last_packet_time = utime.ticks_ms()
            self.timed_out = False

        except Exception:
            self._send_error("PARSE_ERR")

    # ------------------------------------------------------------------
    # Failsafe
    # ------------------------------------------------------------------

    def _check_failsafe(self):
        elapsed = utime.ticks_diff(utime.ticks_ms(), self._last_packet_time)
        if elapsed > self.timeout_ms:
            if not self.timed_out:
                print("!!! COMMS TIMEOUT - ENGAGING FAILSAFE !!!")
                self.timed_out = True
            self.current_cmd = "STOP"
            self.target_speed = 0.0

    # ------------------------------------------------------------------
    # Transmit / Telemetry
    # ------------------------------------------------------------------

    def _send_telemetry(self):
        now = utime.ticks_ms()

        if self.send_speed_enabled:
            if utime.ticks_diff(now, self._last_speed_send) >= self._speed_interval_ms:
                self._send_speed()
                self._last_speed_send = now

        if self.send_battery_enabled:
            if utime.ticks_diff(now, self._last_battery_send) >= self._battery_interval_ms:
                self._send_battery()
                self._last_battery_send = now

    def _send_speed(self):
        msg = f"S:{self.v_left:.2f}:{self.v_right:.2f}\n"
        self.uart.write(msg.encode())

    def _send_battery(self):
        voltage = self._read_battery_voltage()
        msg = f"B:{voltage:.2f}\n"
        self.uart.write(msg.encode())

    def _send_error(self, reason):
        msg = f"E:{reason}\n"
        self.uart.write(msg.encode())

    # ------------------------------------------------------------------
    # Battery ADC
    # ------------------------------------------------------------------

    def _read_battery_voltage(self):
        # Pico ADC reference is 3.3V, 16-bit reading (0-65535)
        # Adjust VOLTAGE_DIVIDER_RATIO to match your hardware voltage divider
        VOLTAGE_DIVIDER_RATIO = 3.0   # e.g. 10k/5k divider for ~9V battery
        raw = self._adc.read_u16()
        voltage = (raw / 65535) * 3.3 * VOLTAGE_DIVIDER_RATIO
        return voltage