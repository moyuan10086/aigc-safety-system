<template>
  <div ref="viewport" class="cockpit-viewport">
    <div class="cockpit-shell" :style="stageStyle">
      <div class="cockpit-ambient" aria-hidden="true"></div>
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const DESIGN_WIDTH = 1920
const DESIGN_HEIGHT = 1080
const viewport = ref<HTMLElement | null>(null)
const scale = ref(1)
const offsetX = ref(0)
const offsetY = ref(0)
let observer: ResizeObserver | null = null

const stageStyle = computed(() => ({
  transform: `translate(${offsetX.value}px, ${offsetY.value}px) scale(${scale.value})`,
}))

function fitStage() {
  const rect = viewport.value?.getBoundingClientRect()
  if (!rect) return
  const nextScale = Math.min(rect.width / DESIGN_WIDTH, rect.height / DESIGN_HEIGHT)
  scale.value = Number.isFinite(nextScale) && nextScale > 0 ? nextScale : 1
  offsetX.value = Math.round((rect.width - DESIGN_WIDTH * scale.value) / 2)
  offsetY.value = Math.round((rect.height - DESIGN_HEIGHT * scale.value) / 2)
}

onMounted(() => {
  fitStage()
  if (viewport.value) {
    observer = new ResizeObserver(fitStage)
    observer.observe(viewport.value)
  }
})
onBeforeUnmount(() => observer?.disconnect())
</script>

<style scoped>
.cockpit-viewport{position:fixed;inset:0;z-index:500;overflow:hidden;background:var(--screen-bg)}
.cockpit-shell{position:absolute;left:0;top:0;display:flex;width:1920px;height:1080px;flex-direction:column;gap:12px;padding:12px 14px 8px;overflow:hidden;color:var(--screen-text-secondary);background:var(--screen-bg);font-family:var(--font-body);transform-origin:0 0}
.cockpit-ambient{position:absolute;inset:0;pointer-events:none;background:radial-gradient(ellipse 46% 44% at 50% 42%,rgba(20,112,192,.18),transparent 68%),radial-gradient(ellipse 34% 32% at 12% 76%,rgba(104,78,224,.10),transparent 66%),radial-gradient(ellipse 30% 30% at 88% 22%,rgba(0,214,208,.07),transparent 66%),linear-gradient(rgba(74,158,208,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(74,158,208,.035) 1px,transparent 1px);background-size:auto,auto,auto,58px 58px,58px 58px}
.cockpit-shell :deep(>*){position:relative;z-index:1;box-sizing:border-box}
:global(body:has(.cockpit-viewport)){overflow:hidden}
</style>
