import unittest

from app.models import CommandType, FlightState
from app.services.state_machine import SafetyStateMachine


class SafetyStateMachineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.machine = SafetyStateMachine()

    def command(self, value: CommandType) -> FlightState:
        accepted, reason, state = self.machine.submit(value)
        self.assertTrue(accepted, reason)
        return state

    def test_nominal_tracking_flight(self) -> None:
        self.assertEqual(self.command(CommandType.CONNECT), FlightState.CONNECTED)
        self.assertEqual(self.command(CommandType.ARM), FlightState.ARMED)
        self.assertEqual(self.command(CommandType.TAKEOFF), FlightState.HOVERING)
        self.assertEqual(self.command(CommandType.START_TRACKING), FlightState.TRACKING)
        self.assertEqual(self.command(CommandType.PAUSE_TRACKING), FlightState.HOVERING)
        self.assertEqual(self.command(CommandType.LAND), FlightState.CONNECTED)

    def test_invalid_command_is_rejected(self) -> None:
        accepted, _, state = self.machine.submit(CommandType.TAKEOFF)
        self.assertFalse(accepted)
        self.assertEqual(state, FlightState.DISCONNECTED)

    def test_emergency_requires_manual_reset(self) -> None:
        self.command(CommandType.CONNECT)
        self.command(CommandType.ARM)
        self.assertEqual(
            self.command(CommandType.EMERGENCY_STOP), FlightState.EMERGENCY
        )
        accepted, _, state = self.machine.submit(CommandType.TAKEOFF)
        self.assertFalse(accepted)
        self.assertEqual(state, FlightState.EMERGENCY)
        self.assertEqual(self.command(CommandType.RESET_FAULT), FlightState.CONNECTED)


if __name__ == "__main__":
    unittest.main()
