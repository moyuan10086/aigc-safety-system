<template>
  <div v-if="samples.length" ref="stripHost" class="sample-strip" :style="stripStyle" @mouseenter="pauseRotation" @mouseleave="startRotation">
    <article v-for="sample in visibleSamples" :key="sample.id" class="sample-card" :class="{ disagreement: sample.disagreement }">
      <div class="sample-media">
        <img :src="sample.image" :alt="sample.title" loading="eager" />
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
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps<{ samples: DemoRiskSample[] }>()
const page = ref(0)
const pageSize = ref(8)
const stripHost = ref<HTMLElement | null>(null)
let rotationTimer: ReturnType<typeof setInterval> | null = null
let resizeObserver: ResizeObserver | null = null
let resizeFrame: number | null = null
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

function scheduleColumns(width: number) {
  if (resizeFrame !== null) cancelAnimationFrame(resizeFrame)
  resizeFrame = requestAnimationFrame(() => {
    updateColumns(width)
    resizeFrame = null
  })
}

function pauseRotation() {
  if (rotationTimer) clearInterval(rotationTimer)
  rotationTimer = null
}

function startRotation() {
  pauseRotation()
  rotationTimer = setInterval(() => {
    const pages = Math.ceil(props.samples.length / pageSize.value)
    if (pages > 1) page.value = (page.value + 1) % pages
  }, 8_000)
}

watch(() => props.samples.length, () => { page.value = 0 })
onMounted(() => {
  startRotation()
  if (stripHost.value) {
    updateColumns(stripHost.value.clientWidth)
    resizeObserver = new ResizeObserver(entries => scheduleColumns(entries[0]?.contentRect.width || 0))
    resizeObserver.observe(stripHost.value)
  }
})
onBeforeUnmount(() => {
  pauseRotation()
  resizeObserver?.disconnect()
  if (resizeFrame !== null) cancelAnimationFrame(resizeFrame)
})
</script>

<style scoped>
.sample-strip{height:100%;display:grid;grid-template-columns:repeat(var(--sample-columns,8),minmax(0,1fr));gap:7px;padding:7px}.sample-card{min-width:0;display:grid;grid-template-rows:minmax(88px,1fr) 64px;overflow:hidden;background:#0a2639;border:1px solid #214b64}.sample-card.disagreement{border-color:#9b7845}.sample-media{position:relative;min-width:0;overflow:hidden;background:#061724}.sample-media img{width:100%;height:100%;display:block;object-fit:cover}.masked-label,.sample-category{position:absolute;padding:2px 5px;font-size:7px;line-height:1.4;background:rgba(4,18,28,.86)}.masked-label{left:5px;top:5px;color:#ffcb78;border:1px solid rgba(255,180,84,.45)}.sample-category{right:5px;bottom:5px;color:#9ceaf4;border:1px solid rgba(49,198,220,.36)}.sample-copy{min-width:0;display:flex;flex-direction:column;padding:6px 7px}.sample-copy header{display:flex;align-items:center;gap:5px}.sample-copy strong{min-width:0;flex:1;overflow:hidden;color:#d9edf7;font-size:8px;text-overflow:ellipsis;white-space:nowrap}.sample-copy b{color:#ffb454;font:7px ui-monospace,monospace;white-space:nowrap}.sample-copy p{display:-webkit-box;margin:3px 0;color:#6f94aa;font-size:7px;line-height:1.35;overflow:hidden;-webkit-box-orient:vertical;-webkit-line-clamp:2}.sample-copy footer{display:flex;align-items:center;gap:5px;margin-top:auto}.sample-copy footer span{min-width:0;flex:1;overflow:hidden;color:#547a8f;font-size:7px;text-overflow:ellipsis;white-space:nowrap}.sample-copy em{flex:0 0 auto;color:#4ddeaa;font-size:7px;font-style:normal;white-space:nowrap}.sample-copy em.alert{color:#ff6d7b}.sample-empty{height:100%;display:grid;place-items:center;color:#52778b;font-size:9px}
</style>
