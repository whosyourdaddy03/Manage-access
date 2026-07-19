from threading import RLock

from app.models import CommandType, FlightState


class SafetyStateMachine:
    """Deterministic command gate used by the mock adapter and unit tests.

    Real flight transitions must be confirmed by PX4 telemetry. The mock version
    moves immediately so the complete browser/API flow can be tested without SITL.
    """

    _transitions: dict[tuple[FlightState, CommandType], FlightState] = {
        (FlightState.DISCONNECTED, CommandType.CONNECT): FlightState.CONNECTED,
        (FlightState.CONNECTED, CommandType.DISCONNECT): FlightState.DISCONNECTED,
        (FlightState.CONNECTED, CommandType.ARM): FlightState.ARMED,
        (FlightState.ARMED, CommandType.DISARM): FlightState.CONNECTED,
        (FlightState.ARMED, CommandType.TAKEOFF): FlightState.HOVERING,
        (FlightState.HOVERING, CommandType.START_TRACKING): FlightState.TRACKING,
        (FlightState.TRACKING, CommandType.PAUSE_TRACKING): FlightState.HOVERING,
        (FlightState.TRACKING, CommandType.HOVER): FlightState.HOVERING,
        (FlightState.TARGET_LOST, CommandType.HOVER): FlightState.HOVERING,
        (FlightState.HOVERING, CommandType.LAND): FlightState.CONNECTED,
        (FlightState.TRACKING, CommandType.LAND): FlightState.CONNECTED,
        (FlightState.TARGET_LOST, CommandType.LAND): FlightState.CONNECTED,
        (FlightState.FAULT, CommandType.LAND): FlightState.CONNECTED,
        (FlightState.FAULT, CommandType.RESET_FAULT): FlightState.CONNECTED,
        (FlightState.EMERGENCY, CommandType.RESET_FAULT): FlightState.CONNECTED,
    }

    def __init__(self) -> None:
        self._state = FlightState.DISCONNECTED
        self._lock = RLock()

    @property
    def state(self) -> FlightState:
        with self._lock:
            return self._state

    def submit(self, command: CommandType) -> tuple[bool, str, FlightState]:
        with self._lock:
            if command is CommandType.EMERGENCY_STOP:
                if self._state is FlightState.DISCONNECTED:
                    return False, "未连接飞行器，无法下发急停", self._state
                self._state = FlightState.EMERGENCY
                return True, "急停已锁定，需要现场检查后人工复位", self._state

            next_state = self._transitions.get((self._state, command))
            if next_state is None:
                return (
                    False,
                    f"状态 {self._state.value} 不允许执行 {command.value}",
                    self._state,
                )

            self._state = next_state
            return True, "模拟适配器已接受并完成命令", self._state
