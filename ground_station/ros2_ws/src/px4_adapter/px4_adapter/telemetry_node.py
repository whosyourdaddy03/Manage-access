import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data

from px4_msgs.msg import VehicleStatus
from uav_interfaces.msg import FlightStatus


class Px4TelemetryAdapter(Node):
    """Read-only first step of the PX4 adapter; it never sends flight commands."""

    def __init__(self) -> None:
        super().__init__("px4_telemetry_adapter")
        self.declare_parameter("vehicle_id", "px4-sitl")
        self.publisher = self.create_publisher(FlightStatus, "/uav/px4_status", 10)
        self.subscription = self.create_subscription(
            VehicleStatus,
            "/fmu/out/vehicle_status",
            self.on_vehicle_status,
            qos_profile_sensor_data,
        )
        self.get_logger().info("Listening for PX4 VehicleStatus over uXRCE-DDS")

    def on_vehicle_status(self, status: VehicleStatus) -> None:
        message = FlightStatus()
        message.header.stamp = self.get_clock().now().to_msg()
        message.vehicle_id = self.get_parameter("vehicle_id").value
        message.source = "px4_uXRCE_DDS"
        message.connected = True
        message.armed = status.arming_state == VehicleStatus.ARMING_STATE_ARMED
        message.flight_state = "ARMED" if message.armed else "CONNECTED"
        message.active_control_source = "PX4"
        self.publisher.publish(message)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = Px4TelemetryAdapter()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
