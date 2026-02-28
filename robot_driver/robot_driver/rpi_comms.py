# rpi_comms.py - Raspberry Pi 4 Serial Communication Module
# Use this on the RPi4 / ROS2 side to talk to the Pico.
#
# Usage (standalone):
#   comms = RpiComms(port="/dev/ttyAMA0")
#   comms.start()
#   comms.send_command("FORWARD", 200.0)
#   print(comms.get_telemetry())
#   comms.stop()
#
# Usage (ROS2 node): instantiate inside your Node, call send_command()
# from your subscriber callbacks, and read telemetry in a timer callback.

import serial
import threading
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("RpiComms")

VALID_COMMANDS = {"FORWARD", "BACKWARD", "LEFT", "RIGHT", "STOP"}


@dataclass
class Telemetry:
    v_left:   float = 0.0
    v_right:  float = 0.0
    battery:  float = 0.0
    last_speed_update:   float = field(default_factory=time.time)
    last_battery_update: float = field(default_factory=time.time)


class RpiComms:
    def __init__(
        self,
        port: str = "/dev/ttyAMA0",
        baudrate: int = 115200,
        timeout_s: float = 1.0,
        rx_poll_hz: int = 200,
    ):
        self._port = port
        self._baudrate = baudrate
        self._timeout_s = timeout_s
        self._poll_interval = 1.0 / rx_poll_hz

        self._serial: Optional[serial.Serial] = None
        self._buf = ""
        self._lock = threading.Lock()          # guards serial writes
        self._telemetry = Telemetry()
        self._telemetry_lock = threading.RLock()

        self._running = False
        self._rx_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        """Open serial port and start background RX thread."""
        self._serial = serial.Serial(
            self._port,
            self._baudrate,
            timeout=0,   # non-blocking reads
        )
        self._running = True
        self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self._rx_thread.start()
        log.info(f"RpiComms started on {self._port} @ {self._baudrate} baud.")

    def stop(self):
        """Stop RX thread and close serial port."""
        self._running = False
        if self._rx_thread:
            self._rx_thread.join(timeout=2.0)
        if self._serial and self._serial.is_open:
            self.send_command("STOP", 0.0)   # safe stop before closing
            self._serial.close()
        log.info("RpiComms stopped.")

    # ------------------------------------------------------------------
    # Send
    # ------------------------------------------------------------------

    def send_command(self, cmd: str, speed: float):
        """Send a command frame to the Pico. Thread-safe."""
        cmd = cmd.upper()
        if cmd not in VALID_COMMANDS:
            log.warning(f"Invalid command: {cmd}")
            return
        if speed < 0:
            log.warning(f"Negative speed rejected: {speed}")
            return

        frame = f"C:{cmd}:{speed:.2f}\n"
        with self._lock:
            if self._serial and self._serial.is_open:
                self._serial.write(frame.encode())

    # ------------------------------------------------------------------
    # Receive
    # ------------------------------------------------------------------

    def _rx_loop(self):
        """Background thread: continuously read and parse incoming frames."""
        while self._running:
            try:
                raw = self._serial.read(128)
                if raw:
                    self._buf += raw.decode("utf-8", errors="ignore")
                    self._process_buffer()
            except serial.SerialException as e:
                log.error(f"Serial read error: {e}")
                break
            time.sleep(self._poll_interval)

    def _process_buffer(self):
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            line = line.strip()
            if line:
                self._parse(line)

    def _parse(self, line: str):
        try:
            parts = line.split(":")
            msg_type = parts[0]

            if msg_type == "S" and len(parts) == 3:
                v_l = float(parts[1])
                v_r = float(parts[2])
                with self._telemetry_lock:
                    self._telemetry.v_left  = v_l
                    self._telemetry.v_right = v_r
                    self._telemetry.last_speed_update = time.time()

            elif msg_type == "B" and len(parts) == 2:
                voltage = float(parts[1])
                with self._telemetry_lock:
                    self._telemetry.battery = voltage
                    self._telemetry.last_battery_update = time.time()

            elif msg_type == "E":
                log.warning(f"Pico error: {':'.join(parts[1:])}")

            else:
                log.debug(f"Unknown frame: {line}")

        except Exception as e:
            log.warning(f"Parse error on '{line}': {e}")

    # ------------------------------------------------------------------
    # Telemetry Access
    # ------------------------------------------------------------------

    def get_telemetry(self) -> Telemetry:
        """Returns a snapshot of the latest telemetry. Thread-safe."""
        with self._telemetry_lock:
            return Telemetry(
                v_left=self._telemetry.v_left,
                v_right=self._telemetry.v_right,
                battery=self._telemetry.battery,
                last_speed_update=self._telemetry.last_speed_update,
                last_battery_update=self._telemetry.last_battery_update,
            )

    def is_stale(self, max_age_s: float = 1.0) -> bool:
        """Returns True if speed telemetry hasn't updated recently (failsafe check)."""
        with self._telemetry_lock:
            return (time.time() - self._telemetry.last_speed_update) > max_age_s


# ------------------------------------------------------------------
# Minimal standalone test
# ------------------------------------------------------------------
if __name__ == "__main__":
    comms = RpiComms(port="/dev/ttyAMA0")
    comms.start()
    time.sleep(1)

    print("Sending FORWARD 200...")
    comms.send_command("FORWARD", 200.0)

    for _ in range(5):
        time.sleep(0.5)
        t = comms.get_telemetry()
        print(f"  L: {t.v_left:.2f}  R: {t.v_right:.2f}  Batt: {t.battery:.2f}V  Stale: {comms.is_stale()}")

    comms.send_command("STOP", 0.0)
    comms.stop()
