import type { CommandResult, CommandType } from '../types'

const apiBase = import.meta.env.VITE_API_BASE_URL || ''

export async function sendCommand(type: CommandType): Promise<CommandResult> {
  const response = await fetch(`${apiBase}/api/v1/commands`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      commandId: crypto.randomUUID(),
      vehicleId: 'px4-sitl',
      type,
      parameters: {},
    }),
  })

  if (!response.ok) {
    throw new Error(`命令接口返回 ${response.status}`)
  }
  return response.json() as Promise<CommandResult>
}

export function telemetryWebSocketUrl(): string {
  if (import.meta.env.VITE_WS_URL) return import.meta.env.VITE_WS_URL
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/api/v1/ws/telemetry`
}
