from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_and_telemetry_contract() -> None:
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["flightAdapter"] == "mock"

    telemetry = client.get("/api/v1/vehicles/primary/telemetry")
    assert telemetry.status_code == 200
    payload = telemetry.json()
    assert payload["vehicleId"] == "px4-sitl"
    assert payload["flightState"] in {"DISCONNECTED", "CONNECTED"}


def test_command_id_is_idempotent() -> None:
    command = {
        "commandId": "221e7994-94be-4745-b771-19b729242990",
        "vehicleId": "px4-sitl",
        "type": "CONNECT",
        "parameters": {},
    }
    first = client.post("/api/v1/commands", json=command)
    second = client.post("/api/v1/commands", json=command)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()


def test_websocket_emits_aliased_telemetry() -> None:
    with client.websocket_connect("/api/v1/ws/telemetry") as socket:
        payload = socket.receive_json()
    assert payload["vehicleId"] == "px4-sitl"
    assert "batteryPercent" in payload
