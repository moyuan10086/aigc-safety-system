<template>
  <section class="card result-card face-panel">
    <div class="panel-heading">
      <div class="heading-title">
        <ScanFace :size="17" aria-hidden="true" />
        <span>人脸与图像质量证据</span>
      </div>
      <span class="scope-label">非身份化检测</span>
    </div>

    <div class="result-body">
      <div class="summary-row">
        <span class="badge" :class="statusClass">{{ statusLabel }}</span>
        <span v-if="evidence.review_recommended" class="review-state">
          <AlertTriangle :size="13" aria-hidden="true" />
          建议人工复核
        </span>
        <span v-else class="pass-state">
          <ShieldCheck :size="13" aria-hidden="true" />
          质量通过
        </span>
      </div>

      <div class="face-metrics">
        <span>清晰度 <b>{{ evidence.sharpness ?? '-' }}</b></span>
        <span>亮度 <b>{{ evidence.brightness ?? '-' }}</b></span>
        <span>主脸占比 <b>{{ percent(evidence.largest_face_ratio) }}</b></span>
        <span>质量 <b>{{ evidence.quality === 'good' ? '良好' : '需复核' }}</b></span>
      </div>

      <ul v-if="evidence.review_reasons?.length" class="reason-list">
        <li v-for="reason in evidence.review_reasons" :key="reason">{{ reason }}</li>
      </ul>

      <div v-if="evidence.faces?.length" class="face-list">
        <div
          v-for="face in evidence.faces"
          :key="face.index"
          class="face-row"
          :class="{ primary: face.index === evidence.primary_face_index }"
        >
          <div class="face-row-heading">
            <span>{{ face.index === evidence.primary_face_index ? '主脸' : '人脸' }} #{{ face.index + 1 }}</span>
            <span class="face-quality" :class="face.quality === 'good' ? 'quality-good' : 'quality-review'">
              {{ face.quality === 'good' ? '质量良好' : '需要复核' }}
            </span>
          </div>
          <div class="face-detail-grid">
            <span>面积占比 <b>{{ percent(face.area_ratio) }}</b></span>
            <span>中心偏移 <b>{{ percent(face.center_offset) }}</b></span>
            <span>边缘余量 <b>{{ percent(face.edge_margin_ratio) }}</b></span>
            <span>局部清晰度 <b>{{ face.sharpness }}</b></span>
            <span>局部亮度 <b>{{ face.brightness }}</b></span>
            <span>位置 <b>{{ boxLabel(face.box) }}</b></span>
          </div>
          <div v-if="face.review_reasons?.length" class="tags">
            <span v-for="reason in face.review_reasons" :key="reason" class="tag tag-danger">{{ reason }}</span>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { AlertTriangle, ScanFace, ShieldCheck } from 'lucide-vue-next'

interface FaceBox {
  x: number
  y: number
  width: number
  height: number
}

interface FaceEvidence {
  index: number
  box: FaceBox
  area_ratio: number
  center_offset: number
  edge_margin_ratio: number
  sharpness: number
  brightness: number
  quality: 'good' | 'review'
  review_reasons: string[]
}

interface Evidence {
  status?: string
  face_detected?: boolean | null
  face_count?: number | null
  sharpness?: number
  brightness?: number
  largest_face_ratio?: number
  quality?: string
  review_recommended?: boolean
  review_reasons?: string[]
  faces?: FaceEvidence[]
  primary_face_index?: number | null
}

const props = defineProps<{ evidence: Evidence }>()

const statusLabel = computed(() => {
  if (props.evidence.status === 'unavailable') return '检测服务不可用'
  if (props.evidence.face_detected) return `检测到 ${props.evidence.face_count ?? 0} 张人脸`
  return '未检测到正脸'
})

const statusClass = computed(() => {
  if (props.evidence.status === 'unavailable') return 'badge-danger'
  if (props.evidence.face_detected && !props.evidence.review_recommended) return 'badge-success'
  return 'badge-warn'
})

const percent = (value?: number | null) =>
  value == null ? '-' : `${(value * 100).toFixed(1)}%`

const boxLabel = (box: FaceBox) => `${box.x},${box.y} / ${box.width}x${box.height}`
</script>

<style scoped>
.face-panel{grid-column:1/-1}.panel-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}.heading-title{display:flex;align-items:center;gap:7px;color:var(--text);font-size:13px;font-weight:700}.heading-title svg{color:var(--primary)}.scope-label{padding:3px 7px;color:var(--muted);background:var(--surface-2);border:1px solid var(--line);border-radius:4px;font-size:10px}.result-body{display:flex;flex-direction:column;gap:10px}.summary-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.review-state,.pass-state{display:inline-flex;align-items:center;gap:5px;font-size:11px}.review-state{color:var(--warning)}.pass-state{color:var(--success)}.badge{display:inline-flex;width:max-content;padding:3px 9px;font-size:11px;font-weight:600}.face-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px}.face-metrics span,.face-detail-grid span{display:flex;justify-content:space-between;gap:8px;padding:7px 8px;color:var(--muted);background:var(--surface-2);border:1px solid var(--line);border-radius:4px;font-size:10px}.face-metrics b,.face-detail-grid b{overflow-wrap:anywhere;color:var(--text);font-family:ui-monospace,monospace;text-align:right}.reason-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;margin:0;padding:0;list-style:none}.reason-list li{position:relative;padding:7px 9px 7px 24px;color:var(--warning);background:rgba(198,137,31,.07);border:1px solid rgba(198,137,31,.2);border-radius:4px;font-size:11px;line-height:1.45}.reason-list li::before{position:absolute;left:9px;content:'!';font-weight:800}.face-list{border-top:1px solid var(--line)}.face-row{padding:12px 0;border-bottom:1px solid var(--line)}.face-row:last-child{padding-bottom:0;border-bottom:0}.face-row.primary{border-left:2px solid var(--primary);padding-left:10px}.face-row-heading{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:8px;color:var(--text);font-size:12px;font-weight:700}.face-quality{font-size:10px;font-weight:600}.quality-good{color:var(--success)}.quality-review{color:var(--warning)}.face-detail-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}.tags{display:flex;flex-wrap:wrap;gap:5px;margin-top:7px}.tag{padding:3px 7px;border-radius:4px;font-size:10px}.tag-danger{color:var(--danger);background:rgba(207,63,79,.08);border:1px solid rgba(207,63,79,.22)}@media(max-width:760px){.face-metrics,.face-detail-grid,.reason-list{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:460px){.face-metrics,.face-detail-grid,.reason-list{grid-template-columns:1fr}.panel-heading{align-items:flex-start;flex-direction:column}}
</style>
