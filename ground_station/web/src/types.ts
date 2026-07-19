export type FlightState =
  | 'DISCONNECTED'
  | 'CONNECTED'
  | 'ARMED'
  | 'TAKING_OFF'
  | 'HOVERING'
  | 'TRACKING'
  | 'TARGET_LOST'
  | 'LANDING'
  | 'FAULT'
  | 'EMERGENCY'

export type CommandType =
  | 'CONNECT'
  | 'DISCONNECT'
  | 'ARM'
  | 'DISARM'
  | 'TAKEOFF'
  | 'HOVER'
  | 'START_TRACKING'
  | 'PAUSE_TRACKING'
  | 'LAND'
  | 'EMERGENCY_STOP'
  | 'RESET_FAULT'

export interface VehicleTelemetry {
  vehicleId: string
  timestamp: string
  source: string
  connected: boolean
  armed: boolean
  flightState: FlightState
  batteryPercent: number
  gpsSatellites: number
  linkQualityPercent: number
  position: {
    latitudeDeg: number
    longitudeDeg: number
    relativeAltitudeM: number
  }
  attitude: {
    rollDeg: number
    pitchDeg: number
    yawDeg: number
  }
  groundSpeedMS: number
  activeControlSource: string
  warnings: string[]
}

export interface CommandResult {
  commandId: string
  accepted: boolean
  reason: string
  currentState: FlightState
  executedAt: string
}
