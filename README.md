# Robot Control - Notes

## Known Hardware Issue: Motor 1 Inverted Wiring

Motor 1 is physically wired in reverse (power wires swapped).
As a workaround, all `motor1_write()` direction booleans in the code are flipped:
- `True` in code = physically spins backward
- `False` in code = physically spins forward

**TODO:** Resolder motor 1 wires to fix this properly. Once resoldered, flip all motor1 direction booleans back to their logical values (FORWARD=True, BACKWARD=False).

## Pin Map

| Component     | Pins     |
|---------------|----------|
| Motor 1       | 6, 7     |
| Motor 2       | 20, 19   |
| Encoder Left  | 2, 3     |
| Encoder Right | 10, 11   |

## Test Sequence

Edit `TEST_SEQUENCE` in `robot_control.py` to change robot behavior.
Each entry is: `("COMMAND", speed_pulses_per_sec, duration_ms)`

Available commands: `FORWARD`, `BACKWARD`, `LEFT`, `RIGHT`, `STOP`