from app.adapters.base import FlightAdapter
from app.models import CommandRequest, CommandResult


class CommandService:
    def __init__(self, adapter: FlightAdapter) -> None:
        self._adapter = adapter
        self._results: dict[str, CommandResult] = {}

    async def submit(self, command: CommandRequest) -> CommandResult:
        key = str(command.command_id)
        if key in self._results:
            return self._results[key]
        result = await self._adapter.execute(command)
        self._results[key] = result
        return result
