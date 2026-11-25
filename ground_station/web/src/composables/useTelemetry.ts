import { onBeforeUnmount, onMounted, ref } from 'vue'
import { telemetryWebSocketUrl } from '../services/api'
import type { VehicleTelemetry } from '../types'

export function useTelemetry() {
  const telemetry = ref<VehicleTelemetry | null>(null)
  const connected = ref(false)
  const lastError = ref('')
  let socket: WebSocket | null = null
  let retryTimer: number | undefined
  let stopped = false

  const connect = () => {
    socket = new WebSocket(telemetryWebSocketUrl())
    socket.onopen = () => {
      connected.value = true
      lastError.value = ''
    }
    socket.onmessage = (event) => {
      telemetry.value = JSON.parse(event.data) as VehicleTelemetry
    }
    socket.onerror = () => {
      lastError.value = '实时遥测连接异常'
    }
    socket.onclose = () => {
      connected.value = false
      if (!stopped) retryTimer = window.setTimeout(connect, 1500)
    }
  }

  onMounted(connect)
  onBeforeUnmount(() => {
    stopped = true
    if (retryTimer) window.clearTimeout(retryTimer)
    socket?.close()
  })

  return { telemetry, connected, lastError }
}
