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
const MIN_DESIGN_HEIGHT = 900
const viewport = ref<HTMLElement | null>(null)
const scale = ref(1)
const offsetX = ref(0)
const offsetY = ref(0)
const stageWidth = ref(DESIGN_WIDTH)
const stageHeight = ref(DESIGN_HEIGHT)
let observer: ResizeObserver | null = null

const stageStyle = computed(() => ({
  transform: `translate(${offsetX.value}px, ${offsetY.value}px) scale(${scale.value})`,
  width: `${stageWidth.value}px`,
  height: `${stageHeight.value}px`,
}))

function fitStage() {
  const rect = viewport.value?.getBoundingClientRect()
  if (!rect) return
  // Scale from width while allowing the logical stage to grow vertically on
  // 16:10 and taller displays. This removes the fixed 1920x1080 letterbox.
  const nextScale = Math.min(rect.width / DESIGN_WIDTH, rect.height / MIN_DESIGN_HEIGHT)
  scale.value = Number.isFinite(nextScale) && nextScale > 0 ? nextScale : 1
  stageWidth.value = Math.max(DESIGN_WIDTH, Math.round(rect.width / scale.value))
  stageHeight.value = Math.max(DESIGN_HEIGHT, Math.round(rect.height / scale.value))
  offsetX.value = Math.round((rect.width - stageWidth.value * scale.value) / 2)
  offsetY.value = Math.round((rect.height - stageHeight.value * scale.value) / 2)
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
.cockpit-shell{position:absolute;left:0;top:0;display:flex;flex-direction:column;gap:12px;padding:12px 14px 8px;overflow:hidden;color:var(--screen-text-secondary);background:var(--screen-bg);font-family:var(--font-body);transform-origin:0 0}
.cockpit-shell::before,.cockpit-shell::after{content:'';position:absolute;z-index:4;inset:8px;pointer-events:none;border:1px solid rgba(42,157,235,.16);clip-path:polygon(0 0,18% 0,18% 1px,82% 1px,82% 0,100% 0,100% 18%,calc(100% - 1px) 18%,calc(100% - 1px) 82%,100% 82%,100% 100%,82% 100%,82% calc(100% - 1px),18% calc(100% - 1px),18% 100%,0 100%,0 82%,1px 82%,1px 18%,0 18%);box-shadow:inset 0 0 42px rgba(0,95,180,.08)}
.cockpit-shell::after{inset:9px;border-color:rgba(0,185,255,.28);opacity:.5;transform:scale(1.001)}
.cockpit-ambient{position:absolute;inset:0;pointer-events:none;background:radial-gradient(ellipse 46% 44% at 50% 42%,rgba(0,96,214,.22),transparent 68%),radial-gradient(ellipse 34% 32% at 12% 76%,rgba(64,71,224,.12),transparent 66%),radial-gradient(ellipse 30% 30% at 88% 22%,rgba(0,142,255,.11),transparent 66%),radial-gradient(circle at 50% 48%,rgba(30,146,255,.10),transparent 20%),linear-gradient(rgba(74,158,208,.04) 1px,transparent 1px),linear-gradient(90deg,rgba(74,158,208,.04) 1px,transparent 1px);background-size:auto,auto,auto,auto,58px 58px,58px 58px}
.cockpit-shell :deep(>*){position:relative;z-index:1;box-sizing:border-box}
:global(body:has(.cockpit-viewport)){overflow:hidden}
</style>
