<template><div ref="host" class="base-chart" role="img" :aria-label="ariaLabel"></div></template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { init, type ECharts, type EChartsCoreOption } from 'echarts/core'
import '../../lib/echarts'

const props = defineProps<{ option: EChartsCoreOption; ariaLabel: string; dark?: boolean }>()
const host = ref<HTMLElement | null>(null)
let chart: ECharts | null = null
let observer: ResizeObserver | null = null

function render() {
  if (!chart) return
  chart.setOption(props.option, { notMerge: true, lazyUpdate: true })
}

onMounted(async () => {
  await nextTick()
  if (!host.value) return
  chart = init(host.value, props.dark ? 'dark' : undefined, { renderer: 'canvas' })
  render()
  observer = new ResizeObserver(() => chart?.resize())
  observer.observe(host.value)
})

watch(() => props.option, render, { deep: true })
onBeforeUnmount(() => {
  observer?.disconnect()
  chart?.dispose()
})
</script>

<style scoped>.base-chart{width:100%;height:100%;min-height:220px}</style>
