<template>
  <section class="card provenance-card" aria-live="polite">
    <div class="headline">
      <div><div class="eyebrow">AI 来源验证</div><h3>{{ result.state_label }}</h3></div>
      <span class="state" :class="result.overall_state">{{ stateText }}</span>
    </div>
    <p class="caveat" v-if="result.overall_state === 'not_found'">未发现兼容水印或来源声明，不代表该图片一定不是 AI 生成。</p>
    <div class="layers">
      <article><b>来源证据</b><span>本地标记：{{ evidenceText(result.source_evidence.local_marker.status) }}</span><span>Content Credentials：尚未启用</span></article>
      <article><b>内容检测</b><span>{{ result.content_detection.note }}</span></article>
      <article><b>审计证据</b><span>SHA-256：{{ shortHash }}</span><span>原图留存：否</span></article>
    </div>
    <details><summary>能力边界与技术信息</summary><ul><li v-for="item in result.limitations" :key="item">{{ item }}</li></ul></details>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ result:any }>()
const stateText = computed(() => ({confirmed_source:'来源确认',not_found:'未发现',inconclusive:'不确定',invalid_or_tampered:'需复核'}[props.result.overall_state] || '未知'))
const shortHash = computed(() => `${props.result.content_hash.slice(0,12)}…${props.result.content_hash.slice(-8)}`)
const evidenceText = (state:string) => ({confirmed_source:'已验证',not_found:'未发现',inconclusive:'证据不足',invalid_or_tampered:'无效'}[state] || state)
</script>

<style scoped>
.provenance-card{grid-column:1/-1;padding:18px}.headline{display:flex;align-items:center;justify-content:space-between;gap:16px}.eyebrow{color:var(--primary);font-size:11px;font-weight:700;letter-spacing:.08em}.headline h3{margin:4px 0 0;color:var(--text);font-size:18px}.state{padding:5px 10px;border-radius:999px;font-size:11px;font-weight:700;background:#edf3f6;color:#476173}.confirmed_source{background:#e7f7f2;color:#087c67}.invalid_or_tampered{background:#fff0f1;color:#bd3042}.inconclusive{background:#fff7e2;color:#966515}.caveat{padding:9px 12px;color:#795c18;background:#fff9e9;border-left:3px solid #d6a42b;font-size:12px}.layers{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:14px}.layers article{display:flex;flex-direction:column;gap:6px;padding:12px;background:var(--surface-2);border:1px solid var(--line);border-radius:7px}.layers b{color:var(--text);font-size:12px}.layers span,details{color:var(--muted);font-size:11px;line-height:1.55}details{margin-top:12px}summary{cursor:pointer}ul{margin-bottom:0;padding-left:18px}@media(max-width:700px){.layers{grid-template-columns:1fr}}
</style>
