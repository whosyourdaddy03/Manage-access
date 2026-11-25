<script setup lang="ts">
import { computed, ref } from 'vue'
import AttitudePanel from './components/AttitudePanel.vue'
import MetricCard from './components/MetricCard.vue'
import { useTelemetry } from './composables/useTelemetry'
import { sendCommand } from './services/api'
import type { CommandType, FlightState } from './types'

const { telemetry, connected: wsConnected, lastError } = useTelemetry()
const busy = ref(false)
const commandMessage = ref('等待操作')
const commandAccepted = ref(true)

const state = computed<FlightState>(() => telemetry.value?.flightState || 'DISCONNECTED')
const stateLabels: Record<FlightState, string> = {
  DISCONNECTED: '未连接', CONNECTED: '已连接', ARMED: '已解锁', TAKING_OFF: '起飞中',
  HOVERING: '悬停', TRACKING: '自主追踪', TARGET_LOST: '目标丢失', LANDING: '降落中',
  FAULT: '故障', EMERGENCY: '紧急锁定',
}

const commandGroups: { label: string; type: CommandType; enabled: FlightState[]; danger?: boolean }[] = [
  { label: '连接 PX4', type: 'CONNECT', enabled: ['DISCONNECTED'] },
  { label: '解锁', type: 'ARM', enabled: ['CONNECTED'] },
  { label: '起飞至悬停', type: 'TAKEOFF', enabled: ['ARMED'] },
  { label: '开始追踪', type: 'START_TRACKING', enabled: ['HOVERING'] },
  { label: '暂停追踪', type: 'PAUSE_TRACKING', enabled: ['TRACKING'] },
  { label: '受控降落', type: 'LAND', enabled: ['HOVERING', 'TRACKING', 'TARGET_LOST', 'FAULT'] },
  { label: '紧急停机', type: 'EMERGENCY_STOP', enabled: ['CONNECTED', 'ARMED', 'HOVERING', 'TRACKING', 'TARGET_LOST', 'FAULT'], danger: true },
  { label: '人工复位', type: 'RESET_FAULT', enabled: ['FAULT', 'EMERGENCY'] },
]

async function execute(type: CommandType) {
  busy.value = true
  try {
    const result = await sendCommand(type)
    commandAccepted.value = result.accepted
    commandMessage.value = `${result.accepted ? '已接受' : '已拒绝'} · ${result.reason}`
  } catch (error) {
    commandAccepted.value = false
    commandMessage.value = error instanceof Error ? error.message : '命令发送失败'
  } finally {
    busy.value = false
  }
}

const n = (value: number | undefined, digits = 1) => value?.toFixed(digits) ?? '--'
</script>

<template>
  <main>
    <header class="topbar">
      <div class="brand-mark"><span></span><span></span><span></span></div>
      <div class="brand">
        <span>PX4 · AUTONOMY LAB</span>
        <h1>研究型无人机地面站</h1>
      </div>
      <div class="header-status">
        <span class="live-dot" :class="{ offline: !wsConnected }"></span>
        <div><small>TELEMETRY</small><strong>{{ wsConnected ? '实时在线' : '正在重连' }}</strong></div>
        <span class="mode-badge">{{ telemetry?.source?.toUpperCase() || 'WAIT' }}</span>
      </div>
    </header>

    <section class="flight-strip">
      <div><span class="eyebrow">FLIGHT STATE</span><strong class="state-name">{{ stateLabels[state] }}</strong></div>
      <div class="state-code">{{ state }}</div>
      <div class="strip-divider"></div>
      <div><span class="eyebrow">CONTROL AUTHORITY</span><strong>{{ telemetry?.activeControlSource || '--' }}</strong></div>
      <div><span class="eyebrow">VEHICLE</span><strong>{{ telemetry?.vehicleId || '等待数据' }}</strong></div>
      <div><span class="eyebrow">ARM STATUS</span><strong :class="{ warning: telemetry?.armed }">{{ telemetry?.armed ? 'ARMED' : 'SAFE' }}</strong></div>
    </section>

    <section class="metrics">
      <MetricCard label="相对高度" :value="n(telemetry?.position.relativeAltitudeM, 2)" unit="m" />
      <MetricCard label="地速" :value="n(telemetry?.groundSpeedMS, 2)" unit="m/s" />
      <MetricCard label="剩余电量" :value="n(telemetry?.batteryPercent, 1)" unit="%" accent="lime" />
      <MetricCard label="GPS 卫星" :value="String(telemetry?.gpsSatellites ?? '--')" unit="颗" accent="amber" />
      <MetricCard label="链路质量" :value="n(telemetry?.linkQualityPercent, 0)" unit="%" />
    </section>

    <section class="workspace">
      <AttitudePanel
        :roll="telemetry?.attitude.rollDeg || 0"
        :pitch="telemetry?.attitude.pitchDeg || 0"
        :yaw="telemetry?.attitude.yawDeg || 0"
      />

      <section class="panel map-panel">
        <div class="panel-heading">
          <div><span class="eyebrow">POSITION</span><h2>位置与航迹</h2></div>
          <span class="mono">WGS 84</span>
        </div>
        <div class="map-grid">
          <div class="radar-ring r1"></div><div class="radar-ring r2"></div><div class="radar-ring r3"></div>
          <div class="route-line"></div>
          <div class="vehicle-pin"><span></span></div>
          <span class="axis north">N</span><span class="axis east">E</span>
        </div>
        <div class="coordinate-row">
          <div><small>LATITUDE</small><strong>{{ n(telemetry?.position.latitudeDeg, 6) }}°</strong></div>
          <div><small>LONGITUDE</small><strong>{{ n(telemetry?.position.longitudeDeg, 6) }}°</strong></div>
        </div>
      </section>

      <section class="panel control-panel">
        <div class="panel-heading">
          <div><span class="eyebrow">COMMAND GATE</span><h2>飞行控制</h2></div>
          <span class="safety-lock">SAFETY ON</span>
        </div>
        <p class="control-note">只提交高层任务请求；连续控制由 ROS 2 安全节点执行。</p>
        <div class="control-grid">
          <button
            v-for="command in commandGroups"
            :key="command.type"
            :class="{ danger: command.danger }"
            :disabled="busy || !command.enabled.includes(state)"
            @click="execute(command.type)"
          >
            <span>{{ command.label }}</span><small>{{ command.type }}</small>
          </button>
        </div>
        <div class="command-feedback" :class="{ rejected: !commandAccepted }">
          <span></span>{{ commandMessage }}
        </div>
      </section>
    </section>

    <section class="bottom-grid">
      <section class="panel alert-panel">
        <div class="panel-heading"><div><span class="eyebrow">SYSTEM EVENTS</span><h2>告警与状态</h2></div></div>
        <div v-if="lastError" class="alert critical">{{ lastError }}</div>
        <div v-for="warning in telemetry?.warnings || ['等待第一帧遥测数据']" :key="warning" class="alert">{{ warning }}</div>
      </section>
      <section class="panel research-panel">
        <div class="panel-heading"><div><span class="eyebrow">RESEARCH MODULES</span><h2>自主飞行链路</h2></div></div>
        <div class="pipeline">
          <span>视觉感知</span><i>→</i><span>目标跟踪</span><i>→</i><span>TD3策略</span><i>→</i><span>安全仲裁</span><i>→</i><span>PX4</span>
        </div>
        <p>基础框架模式：感知与策略节点尚未启动，当前数据来自模拟适配器。</p>
      </section>
    </section>

    <footer>
      <span>QGroundControl 保留用于配置、校准与人工接管</span>
      <span>WEB UI → FASTAPI → ROS 2 → PX4</span>
    </footer>
  </main>
</template>
