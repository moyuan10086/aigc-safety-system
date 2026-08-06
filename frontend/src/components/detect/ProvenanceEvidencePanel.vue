<template>
  <section class="card provenance-card" aria-live="polite">
    <div class="headline">
      <div><div class="eyebrow">AI 来源验证</div><h3>{{ result.state_label }}</h3></div>
      <span class="state" :class="result.overall_state">{{ stateText }}</span>
    </div>
    <p class="caveat" :class="result.overall_state" v-if="caveatText">{{ caveatText }}</p>
    <div class="layers">
      <article><b>来源证据</b><span>本地标记：{{ evidenceText(result.source_evidence.local_marker.status) }}</span><span>Content Credentials：{{ credentialsText }}</span></article>
      <article><b>内容检测</b><span>{{ result.content_detection.note }}</span></article>
      <article><b>审计证据</b><span>SHA-256：{{ shortHash }}</span><span>原图留存：否</span></article>
    </div>
    <div class="metadata-evidence">
      <div class="section-heading"><b>元数据证据</b><span>仅作线索，不代表来源可信</span></div>
      <div class="metadata-grid">
        <span>EXIF：{{ result.metadata?.has_exif ? '存在' : '未发现' }}</span>
        <span>IPTC：{{ iptcText }}</span>
        <span>XMP：{{ result.metadata?.has_xmp ? '存在' : '未发现' }}</span>
        <span>ICC：{{ result.metadata?.has_icc_profile ? '存在' : '未发现' }}</span>
      </div>
      <div v-if="iptcFields.length" class="iptc-fields">
        <span v-for="field in iptcFields" :key="field">{{ field }}</span>
      </div>
    </div>
    <div class="aivo-row">
      <div>
        <b>外部来源复核服务</b>
        <p>AIVO Verify 作为可选的外部复核入口，在其浏览器页面内检查 C2PA、签名和来源时间线；不会改变本平台判定。</p>
      </div>
      <a class="aivo-button" href="https://www.aivo.my/" target="_blank" rel="noopener noreferrer">打开 AIVO Verify</a>
    </div>
    <details><summary>能力边界与技术信息</summary><ul><li v-for="item in result.limitations" :key="item">{{ item }}</li></ul></details>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ result:any }>()
const stateText = computed(() => ({confirmed_source:'来源确认',not_found:'未发现',inconclusive:'不确定',invalid_or_tampered:'需复核'}[props.result.overall_state] || '未知'))
const caveatText = computed(() => ({
  not_found: '未发现兼容水印或来源声明，不代表该图片一定不是 AI 生成。',
  inconclusive: '当前来源证据不足，不能确认来源，请结合内容检测并转人工复核。',
  invalid_or_tampered: '来源声明验证失败或资产可能被篡改，应提升风险并转人工复核。',
}[props.result.overall_state] || ''))
const shortHash = computed(() => `${props.result.content_hash.slice(0,12)}…${props.result.content_hash.slice(-8)}`)
const credentialsText = computed(() => {
  const c = props.result.source_evidence?.content_credentials || {}
  return c.status === 'valid' ? `已验证（${c.manifest_count || 0} 个 manifest）` : c.status === 'invalid_or_tampered' ? '无效或疑似篡改' : c.status === 'inconclusive' ? '证据不足' : c.supported ? '未发现' : '解析器不可用'
})
const evidenceText = (state:string) => ({confirmed_source:'已验证',not_found:'未发现',inconclusive:'证据不足',invalid_or_tampered:'无效'}[state] || state)
const iptcText = computed(() => {
  const iptc = props.result.metadata?.iptc || {}
  if (iptc.status === 'present') return `存在（${iptc.field_count || 0} 个字段）`
  if (iptc.status === 'inconclusive') return '解析不确定'
  return '未发现'
})
const iptcFields = computed(() => {
  const fields = props.result.metadata?.iptc?.fields
  return Array.isArray(fields) ? fields.slice(0, 8) : []
})
</script>

<style scoped>
.provenance-card{grid-column:1/-1;padding:18px}.headline{display:flex;align-items:center;justify-content:space-between;gap:16px}.eyebrow{color:var(--primary);font-size:11px;font-weight:700;letter-spacing:.08em}.headline h3{margin:4px 0 0;color:var(--text);font-size:18px}.state{padding:5px 10px;border-radius:999px;font-size:11px;font-weight:700;background:#edf3f6;color:#476173}.confirmed_source{background:#e7f7f2;color:#087c67}.invalid_or_tampered{background:#fff0f1;color:#bd3042}.inconclusive{background:#fff7e2;color:#966515}.caveat{padding:9px 12px;color:#795c18;background:#fff9e9;border-left:3px solid #d6a42b;font-size:12px}.caveat.invalid_or_tampered{color:#9e2536;background:#fff3f4;border-left-color:#cf3d50}.layers{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:14px}.layers article{display:flex;flex-direction:column;gap:6px;padding:12px;background:var(--surface-2);border:1px solid var(--line);border-radius:7px}.layers b{color:var(--text);font-size:12px}.layers span,details{color:var(--muted);font-size:11px;line-height:1.55}.metadata-evidence{margin-top:12px;padding:12px;background:var(--surface-2);border:1px solid var(--line);border-radius:7px}.section-heading{display:flex;justify-content:space-between;gap:12px;color:var(--text);font-size:12px}.section-heading span{color:var(--muted);font-size:11px;font-weight:400}.metadata-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:10px;color:var(--muted);font-size:11px}.iptc-fields{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}.iptc-fields span{padding:3px 7px;border-radius:4px;background:#eaf6f4;color:#16796f;font-size:10px}.aivo-row{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-top:12px;padding:13px 14px;border:1px solid #cfe5e1;border-radius:7px;background:#f5fbfa}.aivo-row b{color:#174c4b;font-size:13px}.aivo-row p{margin:4px 0 0;color:#5e7778;font-size:11px;line-height:1.45}.aivo-button{flex:0 0 auto;padding:8px 12px;border-radius:5px;background:#147d76;color:#fff;font-size:11px;text-decoration:none;white-space:nowrap}.aivo-button:hover{background:#0d625d}details{margin-top:12px}summary{cursor:pointer}ul{margin-bottom:0;padding-left:18px}@media(max-width:700px){.layers{grid-template-columns:1fr}.metadata-grid{grid-template-columns:repeat(2,1fr)}.aivo-row{align-items:flex-start;flex-direction:column}.aivo-button{width:100%;text-align:center}}
</style>
