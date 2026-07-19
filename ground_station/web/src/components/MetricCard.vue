<script setup lang="ts">
defineProps<{
  label: string
  value: string
  unit?: string
  accent?: 'cyan' | 'lime' | 'amber'
}>()
</script>

<template>
  <article class="metric-card" :data-accent="accent || 'cyan'">
    <span class="metric-label">{{ label }}</span>
    <div><strong>{{ value }}</strong><small v-if="unit">{{ unit }}</small></div>
  </article>
</template>
