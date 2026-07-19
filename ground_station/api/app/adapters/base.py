from typing import Protocol

from app.models import CommandRequest, CommandResult, VehicleTelemetry


class FlightAdapter(Protocol):
    async def execute(self, command: CommandRequest) -> CommandResult: ...

    async def telemetry(self) -> VehicleTelemetry: ...
