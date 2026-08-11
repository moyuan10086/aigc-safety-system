<template>
  <section class="situation-overview">
    <header><span>当前窗口平稳</span><b>近 7 日统计概览</b></header>
    <div class="overview-metrics">
      <article><strong>{{ summary.total_events }}</strong><span>安全事件</span></article>
      <article class="risk"><strong>{{ summary.alerts }}</strong><span>风险告警</span></article>
      <article><strong>{{ summary.blocked }}</strong><span>已阻断</span></article>
      <article><strong>{{ summary.unique_clients }}</strong><span>来源主体</span></article>
    </div>
    <ul v-if="regions.length" class="region-list">
      <li v-for="item in regions.slice(0, 3)" :key="item.region">
        <span>{{ item.region }}</span><i><b :style="{ width: `${regionWidth(item.events)}%` }"></b></i>
        <strong>{{ item.events }}</strong><small>{{ item.alerts }} 告警</small>
      </li>
    </ul>
    <p v-else>暂无来源 IP 记录，等待业务调用接入</p>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

type Summary = { total_events: number; alerts: number; blocked: number; unique_clients: number }
type Region = { region: string; sources: number; events: number; alerts: number; blocked: number }
const props = defineProps<{ summary: Summary; regions: Region[] }>()
const maxEvents = computed(() => Math.max(1, ...props.regions.map(item => item.events)))
const regionWidth = (events: number) => Math.max(8, Math.round(events / maxEvents.value * 100))
</script>

<style scoped>
.situation-overview{display:flex;min-height:0;flex:1;flex-direction:column;padding:10px 13px}.situation-overview>header{display:flex;align-items:center;justify-content:space-between;color:var(--screen-text-muted);font-size:var(--fs-screen-code)}.situation-overview>header span{color:var(--screen-mint)}.situation-overview>header b{font-weight:500}.overview-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin:9px 0}.overview-metrics article{padding:7px 5px;text-align:center;background:rgba(9,45,76,.46);border-bottom:1px solid var(--screen-line-soft)}.overview-metrics strong{display:block;color:var(--screen-text);font:700 18px var(--font-number)}.overview-metrics .risk strong{color:var(--risk-high)}.overview-metrics span{display:block;margin-top:3px;color:var(--screen-text-muted);font-size:var(--fs-screen-code)}.region-list{display:flex;min-height:0;flex:1;flex-direction:column;justify-content:center;gap:8px;margin:0;padding:0;list-style:none}.region-list li{display:grid;grid-template-columns:92px minmax(40px,1fr) 28px 44px;align-items:center;gap:7px;color:var(--screen-text-secondary);font-size:var(--fs-screen-code)}.region-list span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.region-list i{height:4px;overflow:hidden;background:rgba(42,140,255,.10)}.region-list i b{display:block;height:100%;background:linear-gradient(90deg,var(--screen-blue),var(--screen-cyan));box-shadow:0 0 8px var(--screen-blue)}.region-list strong{color:var(--screen-text);font:600 var(--fs-screen-label) var(--font-number);text-align:right}.region-list small{color:var(--screen-text-faint);text-align:right}.situation-overview>p{display:grid;flex:1;place-items:center;margin:0;color:var(--screen-text-faint);font-size:var(--fs-screen-label)}
</style>
