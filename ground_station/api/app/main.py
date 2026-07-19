import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.adapters import MockFlightAdapter
from app.config import settings
from app.models import CommandRequest, CommandResult, VehicleTelemetry
from app.services.command_service import CommandService


if settings.flight_adapter != "mock":
    raise RuntimeError(
        "基础框架目前仅启用 FLIGHT_ADAPTER=mock；ROS 2/PX4 适配入口已在 ros2_ws 中预留"
    )

adapter = MockFlightAdapter()
commands = CommandService(adapter)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.environment,
        "flightAdapter": settings.flight_adapter,
    }


@app.get("/api/v1/vehicles/primary/telemetry", response_model=VehicleTelemetry)
async def current_telemetry() -> VehicleTelemetry:
    return await adapter.telemetry()


@app.post("/api/v1/commands", response_model=CommandResult)
async def submit_command(command: CommandRequest) -> CommandResult:
    return await commands.submit(command)


@app.websocket("/api/v1/ws/telemetry")
async def telemetry_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    period = 1.0 / max(settings.telemetry_hz, 1.0)
    try:
        while True:
            sample = await adapter.telemetry()
            await websocket.send_text(sample.model_dump_json(by_alias=True))
            await asyncio.sleep(period)
    except WebSocketDisconnect:
        return
