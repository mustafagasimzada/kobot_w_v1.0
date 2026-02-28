# kobot_w_v1.0 - Robot Control

## Project Structure

```
kobot_w_v1.0/
├── upy/                        # MicroPython code — flash to Pico
│   ├── main.py                 # Entry point (rename robot_control.py to this)
│   ├── robot_control.py        # Main control loop + threading
│   ├── comms.py                # UART communication, telemetry, failsafe
│   ├── twowheel.py             # Motor driver class
│   ├── PID.py                  # PID controller
│   ├── encoder_portable.py     # Encoder reader
│   ├── motor_test.py           # One-shot motor direction diagnostic
│   ├── led_test.py             # Pico alive check
│   ├── uart_loopback.py        # UART self-test
│   └── uart_scan.py            # Scans all valid UART pin combos
└── robot_driver/               # ROS2 package — lives on RPi4
    ├── package.xml
    ├── setup.py
    ├── setup.cfg
    ├── resource/
    │   └── robot_driver
    └── robot_driver/
        ├── __init__.py
        ├── robot_node.py       # ROS2 node
        └── rpi_comms.py        # Serial comms class for RPi side
```

---

## Hardware

### Pin Map (Pico)

| Component     | Pins       |
|---------------|------------|
| UART1 TX      | GP4        |
| UART1 RX      | GP5        |

### Wiring (Pico to RPi4)

| Pico     | RPi4            | Signal  |
|----------|-----------------|---------|
| GP4 (TX) | GPIO15 (pin 10) | TX → RX |
| GP5 (RX) | GPIO14 (pin 8)  | RX ← TX |
| GND      | GND (pin 6)     | Common ground |

> **Critical:** Make sure GND is shared between Pico and RPi4. Floating ground causes garbled serial data.

---

## Known Hardware Issues

### Motor 1 Inverted Wiring
Motor 1 is physically wired in reverse (power wires swapped).
All `motor1_write()` direction booleans in `robot_control.py` are flipped as a workaround:
- `True` in code = physically spins backward
- `False` in code = physically spins forward

**TODO:** Resolder motor 1 wires. Once fixed, flip all motor1 direction booleans back to logical values (FORWARD=True, BACKWARD=False).

---

## RPi4 Setup

### 1. Enable UART
```bash
sudo nano /boot/firmware/config.txt
```
Add at the bottom:
```
enable_uart=1
dtoverlay=disable-bt
```
Disable Bluetooth services:
```bash
sudo systemctl disable hciuart
sudo systemctl disable bluetooth
sudo reboot
```

### 2. Add user to dialout group
```bash
sudo usermod -aG dialout $USER
```

### 3. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 4. Build ROS2 package
```bash
mkdir -p ~/ros2_ws/src
cp -r robot_driver ~/ros2_ws/src/
cd ~/ros2_ws
colcon build --packages-select robot_driver
source install/setup.bash
```

Add to ~/.bashrc so you don't have to source every time:
```bash
echo "source ~/ros2_ws/install/setup.bash" >> ~/.bashrc
```

---

## Running

### 1. Start the ROS2 node on RPi4
```bash
ros2 run robot_driver robot_node
```

### 2. Control via keyboard (from Docker on your laptop or any ROS2 machine)
```bash
# Start Docker container with network access
xhost +local:docker
docker run -it --network host osrf/ros:humble-desktop bash

# Inside container
source /opt/ros/humble/setup.bash
apt-get install -y ros-humble-teleop-twist-keyboard
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

Keyboard controls:

| Key     | Action                    |
|---------|---------------------------|
| `i`     | Forward                   |
| `,`     | Backward                  |
| `j`     | Left                      |
| `l`     | Right                     |
| `k`     | Stop                      |
| `q`/`z` | Increase/decrease speed   |

### 3. Monitor telemetry (open a second terminal into the same container)
```bash
docker ps                           # get container ID
docker exec -it <container_id> bash
source /opt/ros/humble/setup.bash

ros2 topic echo /wheel_velocities   # left/right encoder speeds
ros2 topic echo /battery_voltage    # battery voltage
ros2 topic hz /wheel_velocities     # verify 20Hz publish rate
```

---

## ROS2 Topics

| Topic               | Type                       | Rate | Description                        |
|---------------------|----------------------------|------|------------------------------------|
| `/cmd_vel`          | geometry_msgs/Twist        | —    | Input velocity commands            |
| `/wheel_velocities` | std_msgs/Float32MultiArray | 20Hz | [left_vel, right_vel] pulses/sec   |
| `/battery_voltage`  | std_msgs/Float32           | 1Hz  | Battery voltage in volts           |

---

## Serial Message Format

### RPi to Pico
```
C:{CMD}:{speed}\n
```
Example: `C:FORWARD:200.00\n`

### Pico to RPi
```
S:{v_left}:{v_right}\n    # 20Hz - wheel velocities
B:{voltage}\n              # 1Hz  - battery voltage
E:{reason}\n               # on error
```

---

## Failsafe Behaviour

- **Pico:** If no command received within 500ms, motors stop automatically. Resumes when comms restore.
- **RPi node:** If `/cmd_vel` goes silent for 500ms, sends STOP to Pico.
- **RPi node:** Logs a warning if Pico telemetry goes stale for more than 1s.

---

## Telemetry Toggles

Disable individual telemetry streams in `comms.py` at runtime:
```python
comms.send_speed_enabled   = False  # disable 20Hz wheel velocity stream
comms.send_battery_enabled = False  # disable 1Hz battery stream
```

---

## PID Tuning

Current values in `robot_control.py`:
```python
pid_left  = PID(kp=150, ki=150, kd=0.1, output_limits=(0, 65535))
pid_right = PID(kp=150, ki=150, kd=0.1, output_limits=(0, 65535))
```
Monitor encoder output while tuning:
```bash
ros2 topic echo /wheel_velocities
```