<template>
  <section class="specialist-evidence" aria-label="成人内容专用检测证据">
    <div class="specialist-head">
      <div>
        <span class="specialist-kicker">LOCAL SPECIALIST</span>
        <h4>成人内容专用检测</h4>
      </div>
      <span class="specialist-status" :class="`status-${evidence.status}`">
        {{ statusLabel }}
      </span>
    </div>

    <div class="specialist-metrics">
      <div><span>最高区域分数</span><b>{{ evidence.adult_score == null ? '不可用' : `${Math.round(evidence.adult_score * 100)}%` }}</b></div>
      <div><span>高风险区域</span><b>{{ evidence.regions?.length || 0 }} 处</b></div>
      <div><span>本地耗时</span><b>{{ evidence.latency_ms ?? 0 }} ms</b></div>
    </div>

    <div v-if="evidence.regions?.length" class="specialist-regions">
      <div v-for="(region, index) in evidence.regions" :key="`${region.class}-${index}`" class="specialist-region">
        <span>{{ region.label }}</span>
        <b>{{ Math.round(region.score * 100) }}%</b>
        <code>[{{ region.box.join(', ') }}]</code>
      </div>
    </div>

    <p class="specialist-note">
      <template v-if="evidence.status === 'not_configured'">专用模型未启用，本项不能据此判定安全。</template>
      <template v-else-if="evidence.status === 'inconclusive'">专用模型本次推理失败，已保留为无法确认。</template>
      <template v-else>本地 NudeNet 仅检测明确裸露区域，不覆盖政治、暴力、武器等类别。</template>
      <span v-if="evidence.shadow_only"> 当前为影子模式，不直接改变最终处置。</span>
    </p>
    <a :href="evidence.source_url" target="_blank" rel="noopener noreferrer" class="specialist-source">
      NudeNet {{ evidence.model_version }} · {{ evidence.license }} · 查看源码
    </a>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ evidence: Record<string, any> }>()
const statusLabel = computed(() => ({
  detected: '发现显式区域',
  not_detected: '未达到阈值',
  inconclusive: '无法确认',
  not_configured: '未启用',
}[props.evidence.status] || '未知状态'))
</script>

<style scoped>
.specialist-evidence { margin-top: 16px; padding: 16px; border: 1px solid #d9e2ec; border-left: 3px solid #2563eb; background: #f8fafc; border-radius: 6px; }
.specialist-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.specialist-kicker { display: block; color: #64748b; font-size: 11px; font-weight: 700; }
.specialist-head h4 { margin: 3px 0 0; color: #172033; font-size: 15px; font-weight: 650; }
.specialist-status { flex: 0 0 auto; padding: 4px 8px; border-radius: 4px; background: #e2e8f0; color: #475569; font-size: 12px; font-weight: 650; }
.status-detected { background: #fee2e2; color: #b42318; }
.status-not_detected { background: #dcfce7; color: #166534; }
.status-inconclusive { background: #fef3c7; color: #92400e; }
.specialist-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin-top: 14px; }
.specialist-metrics div { min-width: 0; padding: 9px 10px; border: 1px solid #e5eaf0; background: #fff; border-radius: 4px; }
.specialist-metrics span { display: block; color: #64748b; font-size: 11px; }
.specialist-metrics b { display: block; margin-top: 3px; color: #172033; font-size: 14px; }
.specialist-regions { margin-top: 10px; }
.specialist-region { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; align-items: center; gap: 10px; padding: 7px 0; border-top: 1px solid #e5eaf0; font-size: 12px; }
.specialist-region code { color: #64748b; font-size: 11px; }
.specialist-note { margin: 12px 0 0; color: #526071; font-size: 12px; line-height: 1.65; }
.specialist-source { display: inline-block; margin-top: 7px; color: #1d4ed8; font-size: 12px; text-decoration: none; }
.specialist-source:hover { text-decoration: underline; }
@media (max-width: 640px) {
  .specialist-metrics { grid-template-columns: 1fr; }
  .specialist-region { grid-template-columns: 1fr auto; }
  .specialist-region code { grid-column: 1 / -1; }
}
</style>
