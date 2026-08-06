<template>
  <div
    v-if="samples.length"
    ref="stripHost"
    class="sample-strip"
    :style="stripStyle"
    @mouseenter="setInteractionPaused(true)"
    @mouseleave="setInteractionPaused(false)"
  >
    <article
      v-for="sample in visibleSamples"
      :key="sample.id"
      class="sample-card"
      :class="{ disagreement: sample.disagreement }"
      :aria-label="`${sample.title}，${sample.result}`"
      tabindex="0"
      @focus="setInteractionPaused(true)"
      @blur="setInteractionPaused(false)"
    >
      <div class="sample-media">
        <img :src="sample.image" :alt="sample.title" loading="eager" decoding="async" />
        <span v-if="sample.masked" class="masked-label">脱敏预览</span>
        <span class="sample-category">{{ sample.risk_category }}</span>
      </div>
      <div class="sample-copy">
        <header><strong>{{ sample.title }}</strong><b>{{ sample.score }}</b></header>
        <p>{{ sample.detail }}</p>
        <footer><span>{{ sample.reference }}</span><em :class="{ alert: sample.disagreement || sample.result === '阻断' }">{{ sample.result }}</em></footer>
      </div>
    </article>
  </div>
  <div v-else class="sample-empty">样本目录加载中</div>
</template>

<script lang="ts">
export interface DemoRiskSample {
  id: string
  title: string
  image: string
  source: string
  reference: string
  risk_category: string
  result: string
  score: string
  detail: string
  disagreement: boolean
  masked: boolean
}
</script>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { createRafScheduler } from '../../lib/scheduling'

const props = defineProps<{ samples: DemoRiskSample[] }>()
const page = ref(0)
const pageSize = ref(8)
const stripHost = ref<HTMLElement | null>(null)
const interactionPaused = ref(false)
let rotationTimer: ReturnType<typeof setInterval> | null = null
let resizeObserver: ResizeObserver | null = null
let motionPreference: MediaQueryList | null = null
const stripStyle = computed(() => ({ '--sample-columns': String(pageSize.value) }))

const visibleSamples = computed(() => {
  const items = props.samples
  if (items.length <= pageSize.value) return items
  const start = page.value * pageSize.value
  return Array.from({ length: pageSize.value }, (_, index) => items[(start + index) % items.length])
})

function updateColumns(width: number) {
  const next = Math.max(4, Math.min(8, Math.floor((width + 7) / 197)))
  if (next !== pageSize.value) {
    pageSize.value = next
    page.value = 0
  }
}

const columnScheduler = createRafScheduler(updateColumns)

function observeStrip() {
  if (!stripHost.value) return
  resizeObserver?.disconnect()
  updateColumns(stripHost.value.clientWidth)
  resizeObserver = new ResizeObserver(entries => {
    columnScheduler.schedule(entries[0]?.contentRect.width || stripHost.value?.clientWidth || 0)
  })
  resizeObserver.observe(stripHost.value)
}

function pauseRotation() {
  if (rotationTimer) clearInterval(rotationTimer)
  rotationTimer = null
}

function startRotation() {
  pauseRotation()
  if (document.hidden || interactionPaused.value || motionPreference?.matches) return
  rotationTimer = setInterval(() => {
    if (stripHost.value?.matches(':hover') || stripHost.value?.contains(document.activeElement)) return
    const pages = Math.ceil(props.samples.length / pageSize.value)
    if (pages > 1) page.value = (page.value + 1) % pages
  }, 8_000)
}

function setInteractionPaused(value: boolean) {
  interactionPaused.value = value
  if (value) pauseRotation()
  else startRotation()
}

function handleVisibilityChange() {
  if (document.hidden) pauseRotation()
  else startRotation()
}

watch(() => props.samples.length, async () => {
  page.value = 0
  await nextTick()
  observeStrip()
})
onMounted(async () => {
  motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)')
  motionPreference.addEventListener('change', startRotation)
  startRotation()
  document.addEventListener('visibilitychange', handleVisibilityChange)
  await nextTick()
  observeStrip()
})
onBeforeUnmount(() => {
  pauseRotation()
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  motionPreference?.removeEventListener('change', startRotation)
  resizeObserver?.disconnect()
  columnScheduler.cancel()
})
</script>

<style scoped>
.sample-strip{height:100%;display:grid;grid-template-columns:repeat(var(--sample-columns,8),minmax(0,1fr));gap:7px;padding:7px}
.sample-card{position:relative;min-width:0;display:grid;grid-template-rows:minmax(88px,1fr) 64px;overflow:hidden;background:#0a2639;border:1px solid #214b64;outline:none;transition:border-color .18s ease,box-shadow .18s ease;--rail:#31c6dc;--scan:rgba(125,232,245,.3);--tick:rgba(125,232,245,.44);--grid:rgba(49,198,220,.13);--vig:rgba(3,16,26,.62)}
.sample-card:not(.disagreement):has(em.alert){--rail:#ff6d7b;--scan:rgba(255,150,158,.34);--tick:rgba(255,150,158,.48);--grid:rgba(255,109,123,.12);--vig:rgba(24,6,10,.6)}
.sample-card.disagreement{border-color:#9b7845;--rail:#ffb454;--scan:rgba(255,203,120,.34);--tick:rgba(255,203,120,.48);--grid:rgba(255,180,84,.13);--vig:rgba(22,14,4,.6)}
.sample-card::after{content:'';position:absolute;left:0;right:0;top:0;z-index:3;height:2px;background:linear-gradient(90deg,var(--rail),rgba(0,0,0,0));opacity:.7;pointer-events:none}
.sample-card:has(em.alert)::after{opacity:.95}
.sample-card:hover{border-color:var(--rail)}
.sample-card:focus-visible{border-color:#7de8f5;box-shadow:inset 0 0 0 1px rgba(125,232,245,.45),0 0 0 1px rgba(125,232,245,.32)}
.sample-media{position:relative;min-width:0;overflow:hidden;background:#061724}
.sample-media img{width:100%;height:100%;display:block;object-fit:cover}
.sample-media::before{content:'';position:absolute;inset:0;z-index:1;pointer-events:none;background:radial-gradient(circle at 50% 50%,rgba(0,0,0,0) 11px,var(--scan) 11px,var(--scan) 12px,rgba(0,0,0,0) 12px),linear-gradient(var(--tick),var(--tick)),linear-gradient(var(--tick),var(--tick)),linear-gradient(var(--grid) 1px,rgba(0,0,0,0) 1px),linear-gradient(90deg,var(--grid) 1px,rgba(0,0,0,0) 1px),radial-gradient(circle at 50% 45%,rgba(0,0,0,0) 52%,var(--vig) 100%);background-size:auto,18px 1px,1px 18px,100% 16px,16px 100%,auto;background-position:50% 50%,50% 50%,50% 50%,0 0,0 0,50% 50%;background-repeat:no-repeat,no-repeat,no-repeat,repeat,repeat,no-repeat;box-shadow:inset 0 0 0 1px var(--scan)}
.sample-media::after{content:'';position:absolute;left:0;right:0;top:0;z-index:1;height:26%;pointer-events:none;background:linear-gradient(180deg,rgba(0,0,0,0),var(--tick));opacity:.34;transition:opacity .18s ease;animation:sample-scan 3.8s linear infinite}
.sample-card:hover .sample-media::after,.sample-card:focus-visible .sample-media::after{opacity:.78}
.sample-card:nth-child(2n) .sample-media::after{animation-delay:-1.1s}
.sample-card:nth-child(3n) .sample-media::after{animation-delay:-2.3s}
@keyframes sample-scan{from{transform:translateY(-110%)}to{transform:translateY(340%)}}
.masked-label,.sample-category{position:absolute;z-index:2;padding:2px 5px;font-size:7px;line-height:1.4;background:rgba(4,18,28,.86)}
.masked-label{left:5px;top:5px;color:#ffcb78;border:1px solid rgba(255,180,84,.45)}
.sample-category{right:5px;bottom:5px;color:#9ceaf4;border:1px solid rgba(49,198,220,.36)}
.sample-copy{min-width:0;display:flex;flex-direction:column;padding:6px 7px;overflow:hidden}
.sample-copy header{display:flex;align-items:center;gap:5px}
.sample-copy strong{min-width:0;flex:1;overflow:hidden;color:#d9edf7;font-size:8px;text-overflow:ellipsis;white-space:nowrap}
.sample-copy b{flex:0 0 auto;padding:1px 4px;color:var(--rail);font:7px ui-monospace,monospace;font-variant-numeric:tabular-nums;letter-spacing:.3px;white-space:nowrap;background:var(--grid);box-shadow:inset 0 0 0 1px var(--scan)}
.sample-copy p{display:-webkit-box;margin:2px 0;color:#6f94aa;font-size:7px;line-height:1.35;overflow:hidden;-webkit-box-orient:vertical;-webkit-line-clamp:2}
.sample-copy footer{display:flex;align-items:center;gap:5px;margin-top:auto}
.sample-copy footer span{min-width:0;flex:1;overflow:hidden;color:#547a8f;font-size:7px;text-overflow:ellipsis;white-space:nowrap}
.sample-copy em{flex:0 0 auto;padding:1px 4px;color:#4ddeaa;font-size:7px;font-style:normal;font-weight:600;white-space:nowrap;background:rgba(77,222,170,.1);box-shadow:inset 0 0 0 1px rgba(77,222,170,.34)}
.sample-copy em::before{content:'';display:inline-block;width:3px;height:3px;margin-right:3px;border-radius:50%;background:currentColor;vertical-align:middle}
.sample-copy em.alert{color:#ff6d7b;background:rgba(255,109,123,.13);box-shadow:inset 0 0 0 1px rgba(255,109,123,.38)}
.sample-card.disagreement .sample-copy em.alert{color:#ffb454;background:rgba(255,180,84,.13);box-shadow:inset 0 0 0 1px rgba(255,180,84,.4)}
.sample-empty{height:100%;display:grid;place-items:center;color:#52778b;font-size:9px}
@media (prefers-reduced-motion:reduce){.sample-card,.sample-media::after{transition:none}.sample-media::after{top:38%;opacity:.32;animation:none}}

.sample-card{border-color:var(--screen-line);background:var(--screen-surface)}
.sample-card:not(.disagreement):has(em.alert){--rail:var(--risk-critical)}
.sample-card.disagreement{border-color:var(--risk-medium);--rail:var(--risk-medium)}
.sample-copy strong{color:var(--screen-text)}
.sample-copy p{color:var(--screen-text-muted)}
.sample-copy footer span{color:var(--screen-text-faint)}
</style>
