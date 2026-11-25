from dataclasses import dataclass
from datetime import datetime, timezone

import rclpy
from rclpy.node import Node

from uav_interfaces.msg import FlightStatus
from uav_interfaces.srv import SubmitCommand


@dataclass(frozen=True)
class Transition:
    source: str
    command: str
    target: str


TRANSITIONS = {
    (item.source, item.command): item.target
    for item in (
        Transition("DISCONNECTED", "CONNECT", "CONNECTED"),
        Transition("CONNECTED", "DISCONNECT", "DISCONNECTED"),
        Transition("CONNECTED", "ARM", "ARMED"),
        Transition("ARMED", "DISARM", "CONNECTED"),
        Transition("ARMED", "TAKEOFF", "HOVERING"),
        Transition("HOVERING", "START_TRACKING", "TRACKING"),
        Transition("TRACKING", "PAUSE_TRACKING", "HOVERING"),
        Transition("HOVERING", "LAND", "CONNECTED"),
        Transition("TRACKING", "LAND", "CONNECTED"),
        Transition("EMERGENCY", "RESET_FAULT", "CONNECTED"),
        Transition("FAULT", "RESET_FAULT", "CONNECTED"),
    )
}


class SafetySupervisor(Node):
    """Safe-by-default state gate with no PX4 actuator output in this version."""

    def __init__(self) -> None:
        super().__init__("safety_supervisor")
        self.declare_parameter("vehicle_id", "px4-sitl")
        self.declare_parameter("simulation_mode", True)
        self.state = "DISCONNECTED"
        self.status_publisher = self.create_publisher(
            FlightStatus, "/uav/safety_status", 10
        )
        self.service = self.create_service(
            SubmitCommand, "/uav/submit_command", self.handle_command
        )
        self.timer = self.create_timer(0.1, self.publish_status)
        self.get_logger().warning(
            "Safety skeleton started: PX4 actuator forwarding is intentionally disabled"
        )

    def handle_command(self, request, response):
        command = request.command_type.upper()
        if command == "EMERGENCY_STOP" and self.state != "DISCONNECTED":
            self.state = "EMERGENCY"
            accepted = True
            reason = "Emergency state locked; actuator forwarding is not implemented"
        else:
            target = TRANSITIONS.get((self.state, command))
            accepted = target is not None
            reason = (
                "Validated in simulation-only safety skeleton"
                if accepted
                else f"Command {command} is invalid while state is {self.state}"
            )
            if target:
                self.state = target

        response.accepted = accepted
        response.reason = reason
        response.current_state = self.state
        now = datetime.now(timezone.utc)
        response.executed_at.sec = int(now.timestamp())
        response.executed_at.nanosec = now.microsecond * 1000
        return response

    def publish_status(self) -> None:
        message = FlightStatus()
        message.header.stamp = self.get_clock().now().to_msg()
        message.vehicle_id = self.get_parameter("vehicle_id").value
        message.source = "uav_safety"
        message.flight_state = self.state
        message.connected = self.state != "DISCONNECTED"
        message.armed = self.state in {"ARMED", "HOVERING", "TRACKING", "EMERGENCY"}
        message.active_control_source = (
            "ROS2_OFFBOARD" if self.state == "TRACKING" else "PX4"
        )
        message.warnings = ["PX4 actuator forwarding disabled in foundation version"]
        self.status_publisher.publish(message)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SafetySupervisor()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
