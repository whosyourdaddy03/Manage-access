<script setup lang="ts">
defineProps<{ roll: number; pitch: number; yaw: number }>()
</script>

<template>
  <section class="panel attitude-panel">
    <div class="panel-heading">
      <div><span class="eyebrow">NAVIGATION</span><h2>姿态仪</h2></div>
      <span class="mono">YAW {{ yaw.toFixed(1) }}°</span>
    </div>
    <div class="attitude-stage">
      <div
        class="horizon"
        :style="{ transform: `translateY(${pitch * 1.4}px) rotate(${-roll}deg)` }"
      >
        <div class="sky"></div>
        <div class="earth"></div>
        <div class="horizon-line"></div>
      </div>
      <div class="crosshair"><i></i><b></b><i></i></div>
      <div class="attitude-readout left">R<br /><strong>{{ roll.toFixed(1) }}°</strong></div>
      <div class="attitude-readout right">P<br /><strong>{{ pitch.toFixed(1) }}°</strong></div>
    </div>
  </section>
</template>
