#!/usr/bin/env python3
# robot_node.py - ROS2 Humble node for Pico robot
#
# Subscribes:  /cmd_vel (geometry_msgs/Twist)
# Publishes:   /wheel_velocities (std_msgs/Float32MultiArray) @ 20Hz
#              /battery_voltage  (std_msgs/Float32)           @  1Hz
#
# Run: ros2 run <your_package> robot_node
# Or:  python3 robot_node.py

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from geometry_msgs.msg import Twist
from std_msgs.msg import Float32, Float32MultiArray

from robot_driver.rpi_comms import RpiComms

# --- Conversion constants ---
# Tune these to match your robot geometry
WHEEL_SEPARATION  = 0.15    # metres between wheels
MAX_SPEED_PULSES  = 2000.0   # pulses/sec at full throttle
MAX_LINEAR_VEL    = 0.5     # m/s max from cmd_vel
MAX_ANGULAR_VEL   = 2.0     # rad/s max from cmd_vel


def twist_to_command(linear_x: float, angular_z: float):
    """
    Convert a Twist message to a (command, speed) pair for the Pico.
    Uses simple differential drive decomposition.
    Returns: (cmd_str, speed_pulses)
    """
    # Clamp inputs
    linear_x  = max(-MAX_LINEAR_VEL,  min(MAX_LINEAR_VEL,  linear_x))
    angular_z = max(-MAX_ANGULAR_VEL, min(MAX_ANGULAR_VEL, angular_z))

    # Normalise to -1..1
    lin = linear_x  / MAX_LINEAR_VEL
    ang = angular_z / MAX_ANGULAR_VEL

    # Dead zone
    if abs(lin) < 0.05 and abs(ang) < 0.05:
        return "STOP", 0.0

    speed = abs(lin) * MAX_SPEED_PULSES

    if abs(ang) > abs(lin):
        # Turning dominates
        cmd = "LEFT" if angular_z > 0 else "RIGHT"
        speed = abs(ang) * MAX_SPEED_PULSES
    elif linear_x >= 0:
        cmd = "FORWARD"
    else:
        cmd = "BACKWARD"

    return cmd, round(speed, 2)


class RobotNode(Node):
    def __init__(self):
        super().__init__("robot_node")

        # --- Parameters ---
        self.declare_parameter("serial_port", "/dev/ttyAMA0")
        self.declare_parameter("baudrate", 115200)
        self.declare_parameter("cmd_vel_timeout_s", 0.5)
        self.declare_parameter("stale_threshold_s", 1.0)

        port     = self.get_parameter("serial_port").value
        baudrate = self.get_parameter("baudrate").value
        self._cmd_timeout = self.get_parameter("cmd_vel_timeout_s").value
        self._stale_thresh = self.get_parameter("stale_threshold_s").value

        # --- Serial comms ---
        self._comms = RpiComms(port=port, baudrate=baudrate)
        self._comms.start()
        self.get_logger().info(f"Serial comms started on {port}")

        # --- QoS ---
        qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)

        # --- Subscribers ---
        self._cmd_vel_sub = self.create_subscription(
            Twist, "/cmd_vel", self._cmd_vel_callback, qos
        )

        # --- Publishers ---
        self._wheel_vel_pub = self.create_publisher(Float32MultiArray, "/wheel_velocities", qos)
        self._battery_pub   = self.create_publisher(Float32, "/battery_voltage", qos)

        # --- Timers ---
        self._telemetry_timer = self.create_timer(0.05,  self._publish_telemetry)   # 20Hz
        self._battery_timer   = self.create_timer(1.0,   self._publish_battery)     # 1Hz
        self._watchdog_timer  = self.create_timer(0.1,   self._watchdog)            # 10Hz

        # --- State ---
        self._last_cmd_time = self.get_clock().now()

        self.get_logger().info("Robot node ready.")

    # ------------------------------------------------------------------
    # cmd_vel callback
    # ------------------------------------------------------------------

    def _cmd_vel_callback(self, msg: Twist):
        self._last_cmd_time = self.get_clock().now()
        cmd, speed = twist_to_command(msg.linear.x, msg.angular.z)
        self._comms.send_command(cmd, speed)

    # ------------------------------------------------------------------
    # Watchdog - stop robot if cmd_vel goes silent
    # ------------------------------------------------------------------

    def _watchdog(self):
        elapsed = (self.get_clock().now() - self._last_cmd_time).nanoseconds / 1e9
        if elapsed > self._cmd_timeout:
            self._comms.send_command("STOP", 0.0)

        if self._comms.is_stale(self._stale_thresh):
            self.get_logger().warn("Pico telemetry stale - check serial connection", throttle_duration_sec=5.0)

    # ------------------------------------------------------------------
    # Telemetry publishers
    # ------------------------------------------------------------------

    def _publish_telemetry(self):
        t = self._comms.get_telemetry()
        msg = Float32MultiArray()
        msg.data = [float(t.v_left), float(t.v_right)]
        self._wheel_vel_pub.publish(msg)

    def _publish_battery(self):
        t = self._comms.get_telemetry()
        msg = Float32()
        msg.data = float(t.battery)
        self._battery_pub.publish(msg)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def destroy_node(self):
        self.get_logger().info("Shutting down - stopping robot...")
        self._comms.send_command("STOP", 0.0)
        self._comms.stop()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = RobotNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
