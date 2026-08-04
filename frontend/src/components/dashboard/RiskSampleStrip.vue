<template>
  <div v-if="samples.length" class="sample-strip">
    <article v-for="sample in samples.slice(0, 8)" :key="sample.id" class="sample-card" :class="{ disagreement: sample.disagreement }">
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
defineProps<{ samples: DemoRiskSample[] }>()
</script>

<style scoped>
.sample-strip{height:100%;display:grid;grid-template-columns:repeat(8,minmax(0,1fr));gap:7px;padding:7px}.sample-card{min-width:0;display:grid;grid-template-rows:74px minmax(0,1fr);overflow:hidden;background:#0a2639;border:1px solid #214b64}.sample-card.disagreement{border-color:#9b7845}.sample-media{position:relative;min-width:0;overflow:hidden;background:#061724}.sample-media img{width:100%;height:100%;display:block;object-fit:cover}.masked-label,.sample-category{position:absolute;padding:2px 5px;font-size:7px;line-height:1.4;background:rgba(4,18,28,.86)}.masked-label{left:5px;top:5px;color:#ffcb78;border:1px solid rgba(255,180,84,.45)}.sample-category{right:5px;bottom:5px;color:#9ceaf4;border:1px solid rgba(49,198,220,.36)}.sample-copy{min-width:0;padding:6px 7px}.sample-copy header{display:flex;align-items:center;gap:5px}.sample-copy strong{min-width:0;flex:1;overflow:hidden;color:#d9edf7;font-size:8px;text-overflow:ellipsis;white-space:nowrap}.sample-copy b{color:#ffb454;font:7px ui-monospace,monospace;white-space:nowrap}.sample-copy p{margin:4px 0;color:#6f94aa;font-size:7px;line-height:1.35;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.sample-copy footer{display:flex;align-items:center;gap:5px}.sample-copy footer span{min-width:0;flex:1;overflow:hidden;color:#547a8f;font-size:7px;text-overflow:ellipsis;white-space:nowrap}.sample-copy em{color:#4ddeaa;font-size:7px;font-style:normal}.sample-copy em.alert{color:#ff6d7b}.sample-empty{height:100%;display:grid;place-items:center;color:#52778b;font-size:9px}@media(max-width:1420px){.sample-strip{grid-template-columns:repeat(6,minmax(0,1fr))}.sample-card:nth-child(n+7){display:none}}
</style>
