import math
import time

from app.models import (
    Attitude,
    CommandRequest,
    CommandResult,
    FlightState,
    Position,
    VehicleTelemetry,
)
from app.services.state_machine import SafetyStateMachine


class MockFlightAdapter:
    """PX4-like deterministic telemetry for UI development without flight hardware."""

    def __init__(self) -> None:
        self.state_machine = SafetyStateMachine()
        self.started_at = time.monotonic()

    async def execute(self, command: CommandRequest) -> CommandResult:
        accepted, reason, state = self.state_machine.submit(command.type)
        return CommandResult(
            commandId=command.command_id,
            accepted=accepted,
            reason=reason,
            currentState=state,
        )

    async def telemetry(self) -> VehicleTelemetry:
        elapsed = time.monotonic() - self.started_at
        state = self.state_machine.state
        connected = state is not FlightState.DISCONNECTED
        flying = state in {
            FlightState.HOVERING,
            FlightState.TRACKING,
            FlightState.TARGET_LOST,
        }
        armed = flying or state in {FlightState.ARMED, FlightState.EMERGENCY}
        altitude = 2.0 + math.sin(elapsed * 0.35) * 0.04 if flying else 0.0
        motion = 1.0 if state is FlightState.TRACKING else 0.15 if flying else 0.0

        return VehicleTelemetry(
            vehicleId="px4-sitl",
            source="mock",
            connected=connected,
            armed=armed,
            flightState=state,
            batteryPercent=max(20.0, 94.0 - elapsed / 600),
            gpsSatellites=14 if connected else 0,
            linkQualityPercent=98.0 if connected else 0.0,
            position=Position(
                latitudeDeg=31.2304 + math.sin(elapsed * 0.02) * 0.00003 * motion,
                longitudeDeg=121.4737 + math.cos(elapsed * 0.02) * 0.00003 * motion,
                relativeAltitudeM=altitude,
            ),
            attitude=Attitude(
                rollDeg=math.sin(elapsed) * 1.2 * motion,
                pitchDeg=math.cos(elapsed * 0.8) * 1.0 * motion,
                yawDeg=(elapsed * 4.0) % 360 if flying else 0.0,
            ),
            groundSpeedMS=0.8 * motion,
            activeControlSource="ROS2_OFFBOARD" if state is FlightState.TRACKING else "PX4",
            warnings=(
                ["模拟数据：尚未连接 PX4 SITL 或实机"]
                if connected
                else ["飞行器未连接"]
            ),
        )
