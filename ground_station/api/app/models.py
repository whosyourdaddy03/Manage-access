from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FlightState(StrEnum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTED = "CONNECTED"
    ARMED = "ARMED"
    TAKING_OFF = "TAKING_OFF"
    HOVERING = "HOVERING"
    TRACKING = "TRACKING"
    TARGET_LOST = "TARGET_LOST"
    LANDING = "LANDING"
    FAULT = "FAULT"
    EMERGENCY = "EMERGENCY"


class CommandType(StrEnum):
    CONNECT = "CONNECT"
    DISCONNECT = "DISCONNECT"
    ARM = "ARM"
    DISARM = "DISARM"
    TAKEOFF = "TAKEOFF"
    HOVER = "HOVER"
    START_TRACKING = "START_TRACKING"
    PAUSE_TRACKING = "PAUSE_TRACKING"
    LAND = "LAND"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    RESET_FAULT = "RESET_FAULT"


class CommandRequest(BaseModel):
    command_id: UUID = Field(default_factory=uuid4, alias="commandId")
    vehicle_id: str = Field(default="px4-sitl", alias="vehicleId", min_length=1)
    type: CommandType
    parameters: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class CommandResult(BaseModel):
    command_id: UUID = Field(alias="commandId")
    accepted: bool
    reason: str
    current_state: FlightState = Field(alias="currentState")
    executed_at: datetime = Field(default_factory=utc_now, alias="executedAt")

    model_config = {"populate_by_name": True}


class Position(BaseModel):
    latitude_deg: float = Field(alias="latitudeDeg")
    longitude_deg: float = Field(alias="longitudeDeg")
    relative_altitude_m: float = Field(alias="relativeAltitudeM")

    model_config = {"populate_by_name": True}


class Attitude(BaseModel):
    roll_deg: float = Field(alias="rollDeg")
    pitch_deg: float = Field(alias="pitchDeg")
    yaw_deg: float = Field(alias="yawDeg")

    model_config = {"populate_by_name": True}


class VehicleTelemetry(BaseModel):
    vehicle_id: str = Field(alias="vehicleId")
    timestamp: datetime = Field(default_factory=utc_now)
    source: str
    connected: bool
    armed: bool
    flight_state: FlightState = Field(alias="flightState")
    battery_percent: float = Field(alias="batteryPercent", ge=0, le=100)
    gps_satellites: int = Field(alias="gpsSatellites", ge=0)
    link_quality_percent: float = Field(alias="linkQualityPercent", ge=0, le=100)
    position: Position
    attitude: Attitude
    ground_speed_m_s: float = Field(alias="groundSpeedMS", ge=0)
    active_control_source: str = Field(alias="activeControlSource")
    warnings: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}
