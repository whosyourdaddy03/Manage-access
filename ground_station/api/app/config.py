from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "PX4 Research Ground Station")
    environment: str = os.getenv("APP_ENV", "development")
    flight_adapter: str = os.getenv("FLIGHT_ADAPTER", "mock")
    cors_origins: tuple[str, ...] = tuple(
        item.strip()
        for item in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        if item.strip()
    )
    telemetry_hz: float = float(os.getenv("TELEMETRY_HZ", "10"))


settings = Settings()
