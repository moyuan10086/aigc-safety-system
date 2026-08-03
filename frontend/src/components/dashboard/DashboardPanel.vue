<template>
  <section class="dashboard-panel">
    <header>
      <div><h2>{{ title }}</h2><p v-if="subtitle">{{ subtitle }}</p></div>
      <slot name="action" />
    </header>
    <div class="panel-body"><slot /></div>
  </section>
</template>

<script setup lang="ts">defineProps<{ title: string; subtitle?: string }>()</script>

<style scoped>
.dashboard-panel{min-width:0;background:var(--surface);border:1px solid var(--line);border-radius:8px;box-shadow:var(--shadow-sm);overflow:hidden}.dashboard-panel>header{height:54px;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:0 16px;border-bottom:1px solid var(--line)}h2{margin:0;color:var(--text);font-size:13px;font-weight:700}p{margin:3px 0 0;color:var(--faint);font-size:10px}.panel-body{min-height:0;padding:14px 16px}
</style>
