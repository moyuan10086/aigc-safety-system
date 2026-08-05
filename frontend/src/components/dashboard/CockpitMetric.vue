<template>
  <article class="cockpit-metric" :class="tone">
    <span class="metric-emblem"><slot name="icon" /></span>
    <span class="metric-copy"><b>{{ label }}</b><small>{{ subtitle }}</small></span>
    <strong ref="valueHost">{{ value }}</strong>
  </article>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { CountUp } from 'countup.js'

const props = withDefaults(defineProps<{
  label: string
  subtitle: string
  value: number
  tone?: 'blue' | 'cyan' | 'mint' | 'red'
}>(), { tone: 'blue' })

const valueHost = ref<HTMLElement | null>(null)
let counter: CountUp | null = null

onMounted(() => {
  if (!valueHost.value) return
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  counter = new CountUp(valueHost.value, props.value, {
    duration: reducedMotion ? 0 : 0.9,
    useGrouping: true,
  })
  if (!counter.error) counter.start()
})

watch(() => props.value, value => counter?.update(value))
onBeforeUnmount(() => counter?.reset())
</script>

<style scoped>
.cockpit-metric{--metric:#25bfff;--metric-deep:#07518c;position:relative;min-width:0;height:100%;display:grid;grid-template-columns:42px minmax(0,1fr) auto;align-items:center;column-gap:10px;padding:8px 13px 8px 11px;overflow:hidden;background:linear-gradient(132deg,rgba(10,52,81,.97),rgba(4,23,39,.98) 76%);border:1px solid rgba(51,142,192,.72);border-left:3px solid var(--metric);clip-path:polygon(0 7px,7px 0,100% 0,100% calc(100% - 7px),calc(100% - 7px) 100%,0 100%);box-shadow:inset 0 1px rgba(122,223,255,.08)}
.cockpit-metric::after{content:'';position:absolute;inset:0;pointer-events:none;background:linear-gradient(100deg,transparent 0 72%,rgba(86,205,255,.08));mix-blend-mode:screen}
.metric-emblem{position:relative;width:38px;height:42px;display:grid;place-items:center;color:#d7f5ff;background:linear-gradient(145deg,var(--metric),var(--metric-deep) 62%,#062e55);clip-path:polygon(50% 0,93% 24%,93% 76%,50% 100%,7% 76%,7% 24%);filter:drop-shadow(0 0 8px color-mix(in srgb,var(--metric) 55%,transparent))}
.metric-emblem::before{content:'';position:absolute;inset:3px;background:linear-gradient(145deg,rgba(189,244,255,.23),rgba(2,29,59,.25));clip-path:inherit}
.metric-emblem::after{content:'';position:absolute;inset:7px;border:1px solid rgba(207,248,255,.24);clip-path:inherit}
.metric-emblem :deep(svg){position:relative;z-index:1;width:19px;height:19px;stroke-width:1.8;filter:drop-shadow(0 0 4px rgba(207,248,255,.72))}
.metric-copy{min-width:0;display:flex;flex-direction:column;gap:5px}.metric-copy b{overflow:hidden;color:#d2e7f0;font-size:11px;font-weight:650;text-overflow:ellipsis;white-space:nowrap}.metric-copy small{overflow:hidden;color:#74a0b5;font:8px ui-monospace,monospace;text-overflow:ellipsis;white-space:nowrap}.cockpit-metric strong{position:relative;z-index:1;color:#f3fbff;font:600 29px/1 ui-monospace,monospace;white-space:nowrap;text-shadow:0 0 12px rgba(116,222,255,.18)}
.cockpit-metric.cyan{--metric:#21d2df;--metric-deep:#076a7a}.cockpit-metric.mint{--metric:#42dcb1;--metric-deep:#087460}.cockpit-metric.red{--metric:#ff536b;--metric-deep:#8f1938}.cockpit-metric.red strong{color:#ff7186;text-shadow:0 0 14px rgba(255,83,107,.34)}
@media(max-width:1199px){.cockpit-metric{grid-template-columns:31px minmax(0,1fr) auto;column-gap:6px;padding:7px 7px}.metric-emblem{width:29px;height:33px}.metric-emblem :deep(svg){width:15px;height:15px}.metric-copy{gap:3px}.metric-copy b{font-size:8px}.metric-copy small{font-size:6px}.cockpit-metric strong{font-size:21px}}
</style>
