<template>
  <article class="metric-card" :class="tone">
    <div class="metric-icon"><component :is="icon" :size="18" /></div>
    <div class="metric-copy"><span>{{ label }}</span><strong>{{ value }}</strong><small>{{ detail }}</small></div>
  </article>
</template>

<script setup lang="ts">
import type { Component } from 'vue'
withDefaults(defineProps<{ icon: Component; label: string; value: string | number; detail: string; tone?: 'primary' | 'danger' | 'warning' | 'success' | 'neutral' }>(), { tone: 'neutral' })
</script>

<style scoped>
.metric-card{height:108px;display:flex;align-items:flex-start;gap:12px;padding:16px;background:var(--surface);border:1px solid var(--line);border-radius:8px;box-shadow:var(--shadow-sm)}.metric-icon{width:36px;height:36px;display:grid;place-items:center;flex:0 0 36px;color:var(--muted);background:var(--surface-3);border-radius:6px}.metric-copy{min-width:0;display:flex;flex-direction:column}.metric-copy span{color:var(--muted);font-size:11px}.metric-copy strong{margin-top:5px;color:var(--text);font-size:24px;line-height:1;font-variant-numeric:tabular-nums}.metric-copy small{margin-top:7px;color:var(--faint);font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.primary .metric-icon{color:var(--primary);background:rgba(8,126,174,.1)}.danger .metric-icon{color:var(--danger);background:rgba(207,63,79,.1)}.warning .metric-icon{color:var(--warning);background:rgba(184,111,18,.1)}.success .metric-icon{color:var(--success);background:rgba(22,128,94,.1)}
</style>
