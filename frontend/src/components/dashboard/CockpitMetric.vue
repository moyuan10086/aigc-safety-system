<template>
  <article class="cockpit-metric" :class="[tone, status, { 'is-alert': alert }]">
    <span class="metric-edge" aria-hidden="true"></span>
    <span class="metric-emblem"><slot name="icon" /></span>
    <span class="metric-copy">
      <b>{{ label }}</b>
      <small>{{ subtitle }}</small>
    </span>
    <strong class="metric-value"><span ref="valueHost">{{ value }}</span></strong>
    <span v-if="alert" class="metric-pulse" aria-hidden="true"></span>
  </article>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { CountUp } from 'countup.js'

const props = withDefaults(defineProps<{
  label: string
  subtitle: string
  value: number
  tone?: 'blue' | 'cyan' | 'violet' | 'mint' | 'red'
  /** 告警态：持续呼吸提示，用于风险告警等需要值守的指标 */
  alert?: boolean
  status?: 'normal' | 'warning' | 'critical'
}>(), { tone: 'blue', alert: false, status: 'normal' })

const valueHost = ref<HTMLElement | null>(null)
let counter: CountUp | null = null

onMounted(() => {
  if (!valueHost.value) return
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  counter = new CountUp(valueHost.value, props.value, {
    duration: reducedMotion ? 0 : 1.1,
    useGrouping: true,
    useEasing: true,
  })
  if (!counter.error) counter.start()
})

// 数字变化时滚动到新值，制造"实时刷新"的运营感
watch(() => props.value, value => counter?.update(value))
onBeforeUnmount(() => counter?.reset())
</script>

<style scoped>
/* KPI 卡：左侧语义色轨 + 六边形徽标 + 大字号数字。
   层级靠"字号 + 字重 + 颜色"三重差异建立，而不是只放大数字。 */
.cockpit-metric{
  --tone:var(--sc-accent);
  --tone-deep:var(--sc-accent-deep);
  position:relative;min-width:0;height:100%;
  display:grid;grid-template-columns:auto minmax(0,1fr) auto;
  align-items:center;column-gap:12px;
  padding:0 var(--sc-pad);
  overflow:hidden;
  border:1px solid var(--sc-line);
  border-radius:var(--sc-radius-sm);
  background:
    radial-gradient(130% 100% at 0 0,var(--tone-soft,rgba(42,201,255,.10)),transparent 62%),
    linear-gradient(140deg,var(--sc-panel-3),rgba(6,24,42,0) 58%),
    var(--sc-panel);
  box-shadow:var(--sc-inset),var(--sc-depth);
}
.cockpit-metric.cyan{--tone:var(--sc-cyan);--tone-deep:var(--sc-cyan-deep);--tone-soft:rgba(34,227,216,.10)}
.cockpit-metric.violet{--tone:var(--sc-violet);--tone-deep:var(--sc-violet-deep);--tone-soft:rgba(143,125,255,.12)}
.cockpit-metric.mint{--tone:var(--sc-mint);--tone-deep:var(--sc-mint-deep);--tone-soft:rgba(60,232,170,.10)}
.cockpit-metric.red{--tone:var(--sc-critical);--tone-deep:#8f1938;--tone-soft:rgba(255,67,99,.12)}

/* 左侧语义色轨 + 顶部渐隐高光，取代原先生硬的 3px 左边框 */
.metric-edge{position:absolute;inset:0;z-index:2;pointer-events:none}
.metric-edge::before{
  content:'';position:absolute;left:0;top:0;bottom:0;width:3px;
  background:linear-gradient(180deg,var(--tone),var(--tone-deep));
  box-shadow:0 0 14px var(--tone);
}
.metric-edge::after{
  content:'';position:absolute;left:3px;right:0;top:0;height:1px;
  background:linear-gradient(90deg,var(--tone),transparent 68%);
  opacity:.5;
}

/* 六边形徽标：内层描边 + 外发光，避免纯色块的廉价感 */
.metric-emblem{
  position:relative;flex:none;width:40px;height:45px;
  display:grid;place-items:center;
  color:#eafaff;
  background:linear-gradient(150deg,var(--tone),var(--tone-deep) 64%,rgba(4,22,38,.9));
  clip-path:polygon(50% 0,93% 25%,93% 75%,50% 100%,7% 75%,7% 25%);
  filter:drop-shadow(0 0 9px color-mix(in srgb,var(--tone) 48%,transparent));
}
.metric-emblem::before{
  content:'';position:absolute;inset:2px;clip-path:inherit;
  background:linear-gradient(150deg,rgba(226,250,255,.30),rgba(2,24,44,.42));
}
.metric-emblem::after{
  content:'';position:absolute;inset:7px;clip-path:inherit;
  border:1px solid rgba(226,250,255,.26);
}
.metric-emblem :deep(svg){
  position:relative;z-index:1;width:20px;height:20px;stroke-width:1.9;
  filter:drop-shadow(0 0 5px rgba(226,250,255,.7));
}

/* 标签用正文档、代号退到最弱档：与数字形成三级落差 */
.metric-copy{min-width:0;display:flex;flex-direction:column;gap:6px}
.metric-copy b{
  overflow:hidden;
  color:var(--sc-ink-2);
  font-family:var(--sc-font);
  font-size:var(--sc-fs-body);
  font-weight:600;
  white-space:nowrap;text-overflow:ellipsis;
}
.metric-copy small{
  overflow:hidden;
  color:var(--sc-ink-4);
  font-family:var(--sc-font-mono);
  font-size:var(--sc-fs-code);
  letter-spacing:.09em;
  white-space:nowrap;text-overflow:ellipsis;
}

/* 数字：最强视觉重量 —— 大字号 + 700 + 字距 + 轻发光 */
.metric-value{
  position:relative;z-index:1;
  color:var(--sc-ink);
  font-family:var(--sc-font-num);
  font-size:var(--sc-fs-kpi);
  font-weight:var(--sc-w-num);
  line-height:1;
  letter-spacing:var(--sc-ls-num);
  font-variant-numeric:tabular-nums;
  white-space:nowrap;
  text-shadow:var(--sc-text-glow);
}
.cockpit-metric.red .metric-value{
  color:#ff8095;
  text-shadow:0 0 20px rgba(255,67,99,.42);
}

/* 告警呼吸：只在告警指标上运行，避免全屏都在闪 */
.metric-pulse{
  position:absolute;inset:-1px;z-index:1;pointer-events:none;
  border-radius:inherit;
  box-shadow:inset 0 0 22px rgba(255,67,99,.20);
  animation:metric-breathe var(--sc-breathe) ease-in-out infinite;
}
@keyframes metric-breathe{0%,100%{opacity:.25}50%{opacity:1}}

@media(max-width:0px){
  .cockpit-metric{column-gap:9px;padding:0 12px}
  .metric-emblem{width:34px;height:39px}
  .metric-emblem :deep(svg){width:17px;height:17px}
  .metric-copy{gap:4px}
}
@media(max-width:0px){
  .cockpit-metric{grid-template-columns:auto minmax(0,1fr);column-gap:8px;padding:0 10px}
  .metric-emblem{width:30px;height:34px}
  .metric-emblem :deep(svg){width:15px;height:15px}
  .metric-value{grid-column:2;grid-row:1}
  .metric-copy{grid-column:2;grid-row:2}
  .metric-copy small{display:none}
}

.cockpit-metric{
  border-color:var(--screen-line-soft);
  border-radius:var(--screen-radius-sm);
  background:linear-gradient(140deg,rgba(10,36,58,.72),rgba(4,16,29,.78));
  box-shadow:0 12px 28px -20px rgba(0,0,0,.8);
}
.cockpit-metric:hover{border-color:var(--screen-line)}
.metric-value{font-size:var(--fs-screen-kpi)}
.metric-copy b{font-size:var(--fs-screen-body)}
.cockpit-metric.warning .metric-value{color:var(--risk-medium)}
.cockpit-metric.critical .metric-value{color:var(--risk-critical)}
</style>
