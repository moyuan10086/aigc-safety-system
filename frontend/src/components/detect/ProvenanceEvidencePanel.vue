<template>
  <section class="card provenance-card" aria-live="polite">
    <div class="headline">
      <div><div class="eyebrow">AI 来源验证</div><h3>{{ primaryTitle }}</h3></div>
      <span class="state" :class="[result.overall_state, { 'ai-generated': providerAttribution.aiGenerated || watermarkPresentation.aiGenerated }]"><component :is="stateIcon" :size="14" />{{ primaryBadge }}</span>
    </div>
    <section class="origin-verdict" :class="{ 'ai-generated': providerAttribution.aiGenerated || watermarkPresentation.aiGenerated }">
      <span class="verdict-icon"><Sparkles v-if="providerAttribution.aiGenerated || watermarkPresentation.aiGenerated" :size="23" /><ShieldCheck v-else :size="22" /></span>
      <div><b>{{ verdictLabel }}</b><p>{{ primaryDescription }}</p></div>
      <span class="confidence">{{ confidenceLabel }}</span>
    </section>

    <dl class="credential-summary">
      <div><dt>生成服务</dt><dd>{{ claimGenerator || '未提供' }}</dd></div>
      <div><dt>C2PA 签名</dt><dd>{{ localVerdictText }}</dd></div>
      <div><dt>数字来源类型</dt><dd>{{ sourceTypeText }}</dd></div>
      <div><dt>具体模型</dt><dd>{{ providerAttribution.aiGenerated ? '凭证未披露' : '无法确认' }}</dd></div>
    </dl>

    <section class="watermark-signal" :class="`watermark-${watermarkPresentation.status}`">
      <span class="watermark-icon"><Fingerprint :size="19" /></span>
      <div><b>{{ watermarkPresentation.title }}</b><p>{{ watermarkPresentation.note }}</p></div>
      <strong>{{ watermarkPresentation.badge }}</strong>
    </section>
    <div v-if="visibleWatermarkCapabilities.length" class="capability-row" aria-label="水印能力状态">
      <span v-for="item in visibleWatermarkCapabilities" :key="item.id" :class="`capability-${item.status}`" :title="item.note">
        {{ item.label }} · {{ capabilityStatus(item.status) }}
      </span>
    </div>

    <details class="technical-evidence">
      <summary><span>查看完整技术证据</span><small>哈希、元数据、活动声明与溯源时间线</small></summary>
      <div class="layers">
        <article><b><Fingerprint :size="16" /> 来源凭证</b><span>Content Credentials：{{ credentialsText }}</span><span>签发服务：{{ claimGenerator || '未提供' }}</span></article>
        <article><b><ScanSearch :size="16" /> 内容检测边界</b><span>{{ result.content_detection.note }}</span></article>
        <article><b><FileKey2 :size="16" /> 审计证据</b><span>SHA-256：{{ shortHash }}</span><span>原图留存：否</span></article>
      </div>
      <div class="metadata-evidence">
        <div class="section-heading"><b>元数据证据</b><span>仅作辅助线索</span></div>
        <div class="metadata-grid">
          <span>EXIF：{{ result.metadata?.has_exif ? '存在' : '未发现' }}</span><span>IPTC：{{ iptcText }}</span><span>XMP：{{ result.metadata?.has_xmp ? '存在' : '未发现' }}</span><span>ICC：{{ result.metadata?.has_icc_profile ? '存在' : '未发现' }}</span>
        </div>
        <div v-if="iptcFields.length" class="iptc-fields"><span v-for="field in iptcFields" :key="field">{{ field }}</span></div>
      </div>
      <section class="local-verification" :class="localVerdictClass">
        <header><div><span class="local-icon"><ShieldCheck :size="19" /></span><span><b>浏览器本地 C2PA 验证</b><small>图片不会再次上传</small></span></div><strong>{{ localVerdictText }}</strong></header>
        <template v-if="localResult && !localResult.error">
          <dl class="credential-details">
            <div><dt>活动声明</dt><dd :title="localResult.activeManifest">{{ localResult.activeManifest || '—' }}</dd></div><div><dt>签发工具</dt><dd>{{ claimGenerator || '未提供' }}</dd></div><div><dt>数字来源类型</dt><dd>{{ sourceTypeText }}</dd></div><div><dt>验证问题</dt><dd>{{ localResult.validationIssues?.length || 0 }} 项</dd></div>
          </dl>
        <ol v-if="localResult.timeline?.length" class="timeline">
          <li v-for="(event, index) in localResult.timeline" :key="`${event.action}-${index}`">
            <span></span><div><b>{{ actionLabel(event.action) }}</b><p>{{ event.description }}</p><time v-if="event.when">{{ event.when }}</time></div>
          </li>
        </ol>
        <details v-if="localResult.validationIssues?.length"><summary>查看验证问题</summary><ul><li v-for="issue in localResult.validationIssues" :key="issue">{{ issue }}</li></ul></details>
        </template>
        <p v-else class="local-error">本地验证引擎未能读取该图片，服务端来源结论仍保留。</p>
      </section>
    </details>
    <p class="evidence-boundary">{{ boundaryText }}</p>
    <details><summary>能力边界与技术信息</summary><ul><li v-for="item in result.limitations" :key="item">{{ item }}</li></ul></details>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CircleAlert, CircleCheckBig, CircleHelp, FileKey2, Fingerprint, ScanSearch, ShieldCheck, Sparkles } from 'lucide-vue-next'
import { getProvenancePresentation } from '../../lib/provenancePresentation'
import { getProviderAttribution } from '../../lib/providerAttribution'
import { getVisibleWatermarkCapabilities, getWatermarkPresentation } from '../../lib/watermarkPresentation'
const props = defineProps<{ result:any }>()
const presentation = computed(() => getProvenancePresentation(props.result.overall_state))
const stateText = computed(() => ({confirmed_source:'凭证有效',not_found:'未发现',inconclusive:'证据不足',invalid_or_tampered:'需复核'}[props.result.overall_state] || '未知'))
const stateIcon = computed(() => props.result.overall_state === 'confirmed_source' ? CircleCheckBig : props.result.overall_state === 'invalid_or_tampered' ? CircleAlert : CircleHelp)
const shortHash = computed(() => `${props.result.content_hash.slice(0,12)}…${props.result.content_hash.slice(-8)}`)
const credentialsText = computed(() => {
  const c = props.result.source_evidence?.content_credentials || {}
  return c.status === 'valid' ? `已验证（${c.manifest_count || 0} 个 manifest）` : c.status === 'invalid_or_tampered' ? '无效或疑似篡改' : c.status === 'inconclusive' ? '证据不足' : c.supported ? '未发现' : '解析器不可用'
})
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
const localResult = computed(() => props.result.local_c2pa)
const claimGenerator = computed(() => localResult.value?.claimGenerator || props.result.source_evidence?.content_credentials?.claim_generator || '')
const credentialsValid = computed(() => props.result.source_evidence?.content_credentials?.status === 'valid' && localResult.value?.verdict !== 'invalid')
const providerAttribution = computed(() => getProviderAttribution(claimGenerator.value, localResult.value?.sourceType || '', credentialsValid.value))
const watermarkPresentation = computed(() => getWatermarkPresentation(props.result.source_evidence?.watermark))
const visibleWatermarkCapabilities = computed(() => getVisibleWatermarkCapabilities(props.result.watermark_capabilities))
const primaryTitle = computed(() => providerAttribution.value.aiGenerated
  ? providerAttribution.value.title
  : watermarkPresentation.value.aiGenerated ? watermarkPresentation.value.title
  : providerAttribution.value.provider !== '未知' ? `${providerAttribution.value.provider} 来源凭证` : presentation.value.label)
const primaryBadge = computed(() => providerAttribution.value.aiGenerated ? 'AI 生成已确认' : watermarkPresentation.value.aiGenerated ? watermarkPresentation.value.badge : stateText.value)
const primaryDescription = computed(() => watermarkPresentation.value.aiGenerated
  ? watermarkPresentation.value.note
  : providerAttribution.value.aiGenerated || providerAttribution.value.provider !== '未知'
  ? providerAttribution.value.note
  : presentation.value.message)
const verdictLabel = computed(() => watermarkPresentation.value.aiGenerated && !providerAttribution.value.aiGenerated ? '平台签名隐形水印判定' : providerAttribution.value.aiGenerated ? 'C2PA 生成来源判定' : '来源证据综合判定')
const confidenceLabel = computed(() => watermarkPresentation.value.aiGenerated && !providerAttribution.value.aiGenerated ? '签名水印已验证' : providerAttribution.value.aiGenerated ? '高可信来源证据' : '来源链核验结果')
const capabilityStatus = (status:string) => ({ available:'已接入', not_configured:'未配置', unsupported_media:'当前不适用' }[status] || status)
const localVerdictClass = computed(() => localResult.value?.error ? 'local-error-state' : `local-${localResult.value?.verdict || 'unavailable'}`)
const localVerdictText = computed(() => ({ verified:'文件绑定验证通过', invalid:'凭证或文件绑定失败', inconclusive:'文件绑定通过，签发方待确认', 'not-found':'未发现凭证' }[localResult.value?.verdict] || '本地验证不可用'))
const sourceTypeText = computed(() => ({
  trainedAlgorithmicMedia: 'AI 生成内容', compositeSynthetic: '合成内容', algorithmicallyEnhanced: '算法增强内容',
  digitalCapture: '数字设备拍摄', humanEdits: '人工编辑内容',
}[localResult.value?.sourceType] || localResult.value?.sourceType || '未声明'))
const boundaryText = computed(() => providerAttribution.value.aiGenerated
  ? `该 AI 生成结论由有效 C2PA 签名、${claimGenerator.value} 签发信息共同支持；凭证未披露具体模型版本，且本结论不评价内容是否安全。`
  : watermarkPresentation.value.aiGenerated
    ? '该结论来自本平台签名隐形水印，只能确认本平台曾标记该内容；不能据此声称由 Google、OpenAI 或其他第三方生成。'
  : 'Content Credentials 可证明声明与文件的绑定及来源链完整性；未明确声明 AI 生成时，不应仅凭厂商或水印线索推断。')
const actionLabel = (action:string) => {
  const value = action.toLowerCase()
  if (value.includes('created')) return '内容创建'
  if (value.includes('opened')) return '打开源文件'
  if (value.includes('placed')) return '素材置入'
  if (value.includes('cropped')) return '画面裁剪'
  if (value.includes('filtered')) return '应用滤镜'
  if (value.includes('published')) return '内容发布'
  return '内容编辑'
}
</script>

<style scoped>
.provenance-card{grid-column:1/-1;padding:18px}.headline{display:flex;align-items:center;justify-content:space-between;gap:16px}.eyebrow{color:var(--primary);font-size:11px;font-weight:700;letter-spacing:.08em}.headline h3{margin:4px 0 0;color:var(--text);font-size:18px}.state{display:inline-flex;align-items:center;gap:6px;padding:6px 11px;border-radius:999px;font-size:11px;font-weight:700;background:#edf3f6;color:#476173}.confirmed_source{background:#e7f7f2;color:#087c67}.invalid_or_tampered{background:#fff0f1;color:#bd3042}.inconclusive{background:#fff7e2;color:#966515}.caveat{display:flex;align-items:flex-start;gap:8px;padding:10px 12px;color:#795c18;background:#fff9e9;border-left:3px solid #d6a42b;font-size:12px;line-height:1.55}.caveat.confirmed_source{color:#11675b;background:#effaf7;border-left-color:#1a9b87}.caveat.invalid_or_tampered{color:#9e2536;background:#fff3f4;border-left-color:#cf3d50}.caveat svg{flex:0 0 auto;margin-top:1px}.layers{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:14px}.layers article{display:flex;flex-direction:column;gap:6px;padding:12px;background:var(--surface-2);border:1px solid var(--line);border-radius:7px}.layers b{display:flex;align-items:center;gap:6px;color:var(--text);font-size:12px}.layers b svg{color:var(--primary)}.layers span,details{color:var(--muted);font-size:11px;line-height:1.55}.metadata-evidence{margin-top:12px;padding:12px;background:var(--surface-2);border:1px solid var(--line);border-radius:7px}.section-heading{display:flex;justify-content:space-between;gap:12px;color:var(--text);font-size:12px}.section-heading span{color:var(--muted);font-size:11px;font-weight:400}.metadata-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:10px;color:var(--muted);font-size:11px}.iptc-fields{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}.iptc-fields span{padding:3px 7px;border-radius:4px;background:#eaf6f4;color:#16796f;font-size:10px}.provider-attribution{margin-top:12px;padding:14px;border:1px solid #cfe0ea;border-radius:7px;background:#f5f9fc}.provider-attribution.known{border-color:#b9dcd5;background:#f3fbf9}.provider-heading{display:flex;align-items:center;gap:9px}.provider-heading>div{display:flex;flex:1;flex-direction:column;gap:2px}.provider-heading b{color:var(--text);font-size:13px}.provider-heading small{color:var(--muted);font-size:10px}.provider-heading>strong{color:#147d76;font-size:12px}.provider-icon{display:grid;place-items:center;width:31px;height:31px;border-radius:6px;background:#e0f3ef;color:#148675}.provider-copy{margin:10px 0 0 40px}.provider-copy h4{margin:0;color:var(--text);font-size:13px}.provider-copy p{margin:4px 0 0;color:var(--muted);font-size:11px;line-height:1.5}.provider-status{display:flex;gap:8px;margin:11px 0 0 40px}.provider-status span{padding:3px 7px;border-radius:4px;background:#eaf1f5;color:#587080;font-size:10px}.provider-status span:first-child{background:#fff3d7;color:#8d671e}.local-verification{margin-top:12px;padding:14px;border:1px solid #d5e3ea;border-radius:7px;background:#f8fbfc}.local-verification.local-verified{border-color:#b9ded5;background:#f3fbf9}.local-verification.local-invalid{border-color:#edc4cb;background:#fff7f8}.local-verification>header,.local-verification>header>div,.local-verification>header span{display:flex;align-items:center}.local-verification>header{justify-content:space-between;gap:16px}.local-verification>header>div{gap:9px}.local-verification>header span{align-items:flex-start;flex-direction:column;gap:2px}.local-verification>header b{color:var(--text);font-size:13px}.local-verification>header small{color:var(--muted);font-size:10px}.local-verification>header strong{color:#147d76;font-size:11px}.local-icon{display:grid!important;place-items:center;width:32px;height:32px;border-radius:6px;background:#e3f5f1;color:#128272}.credential-details{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:14px 0 0;padding-top:12px;border-top:1px solid #dce8ed}.credential-details div{min-width:0}.credential-details dt{color:var(--muted);font-size:10px}.credential-details dd{overflow:hidden;margin:4px 0 0;color:var(--text);font-size:11px;font-weight:600;text-overflow:ellipsis;white-space:nowrap}.timeline{display:flex;flex-wrap:wrap;gap:16px;margin:14px 0 0;padding:0;list-style:none}.timeline li{display:flex;gap:8px;min-width:160px}.timeline li>span{width:7px;height:7px;margin-top:5px;border-radius:50%;background:#1b9c88;box-shadow:0 0 0 4px #dff2ee}.timeline b{color:var(--text);font-size:11px}.timeline p,.timeline time,.local-error,.evidence-boundary{margin:2px 0 0;color:var(--muted);font-size:10px}.evidence-boundary{margin-top:12px;padding-top:10px;border-top:1px solid #dce8ed;line-height:1.55}details{margin-top:12px}summary{cursor:pointer}ul{margin-bottom:0;padding-left:18px}@media(max-width:700px){.layers{grid-template-columns:1fr}.metadata-grid,.credential-details{grid-template-columns:repeat(2,minmax(0,1fr))}.local-verification>header{align-items:flex-start;flex-direction:column}.provider-heading{align-items:flex-start}.provider-heading>strong{margin-left:auto}.provider-copy,.provider-status{margin-left:0}}
.origin-verdict{display:flex;align-items:center;gap:12px;margin-top:14px;padding:14px 16px;border:1px solid #cbdfe8;border-left:4px solid #2c8dac;border-radius:8px;background:linear-gradient(100deg,#f3f9fc,#f9fbfc)}
.origin-verdict.ai-generated{border-color:#acdcd0;border-left-color:#14977f;background:linear-gradient(100deg,#edf9f5,#f8fcfb)}
.verdict-icon{display:grid;flex:0 0 auto;place-items:center;width:42px;height:42px;border-radius:9px;background:#e2f1f6;color:#1684a5}.ai-generated .verdict-icon{background:#dff4ed;color:#0c9278}
.origin-verdict>div{min-width:0;flex:1}.origin-verdict b{color:var(--text);font-size:13px}.origin-verdict p{margin:4px 0 0;color:#536d7d;font-size:12px;line-height:1.55}.confidence{flex:0 0 auto;padding:5px 9px;border-radius:999px;background:#e5f5f1;color:#117c68;font-size:10px;font-weight:700}
.credential-summary{display:grid;grid-template-columns:1.25fr .75fr .8fr .75fr;gap:0;margin:12px 0 0;border:1px solid #d7e3e9;border-radius:8px;background:#fff}.credential-summary div{min-width:0;padding:12px 14px;border-right:1px solid #e1e9ed}.credential-summary div:last-child{border-right:0}.credential-summary dt{color:var(--muted);font-size:10px}.credential-summary dd{overflow:hidden;margin:5px 0 0;color:var(--text);font-size:12px;font-weight:700;text-overflow:ellipsis;white-space:nowrap}
.watermark-signal{display:flex;align-items:center;gap:10px;margin-top:12px;padding:11px 13px;border:1px solid #d8e4e9;border-radius:8px;background:#f8fafb}.watermark-icon{display:grid;flex:0 0 auto;place-items:center;width:34px;height:34px;border-radius:7px;background:#e7f1f5;color:#39798f}.watermark-signal>div{min-width:0;flex:1}.watermark-signal b{color:var(--text);font-size:12px}.watermark-signal p{margin:3px 0 0;color:var(--muted);font-size:10px;line-height:1.45}.watermark-signal strong{color:#587080;font-size:10px}.watermark-confirmed{border-color:#b9dcd5;background:#f3fbf9}.watermark-confirmed .watermark-icon{background:#dff4ed;color:#0c9278}.watermark-confirmed strong{color:#087b66}.watermark-invalid{border-color:#edc4cb;background:#fff7f8}.watermark-invalid .watermark-icon,.watermark-invalid strong{color:#bd3042}.capability-row{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}.capability-row span{padding:4px 7px;border-radius:5px;background:#edf3f6;color:#587080;font-size:9px}.capability-row .capability-available{background:#e7f7f2;color:#087c67}.capability-row .capability-not_configured,.capability-row .capability-unsupported_media{background:#fff7e2;color:#8a651d}
.technical-evidence{margin-top:12px!important;border:1px solid #d8e4e9;border-radius:8px;background:#f8fafb}.technical-evidence>summary{display:flex;align-items:center;justify-content:space-between;padding:11px 13px;color:var(--text);font-size:12px;font-weight:700;list-style:none}.technical-evidence>summary::-webkit-details-marker{display:none}.technical-evidence>summary:after{content:'+';color:var(--primary);font-size:18px;font-weight:400}.technical-evidence[open]>summary:after{content:'−'}.technical-evidence>summary small{margin-left:auto;margin-right:14px;color:var(--muted);font-size:10px;font-weight:400}.technical-evidence>.layers,.technical-evidence>.metadata-evidence,.technical-evidence>.local-verification{margin-left:12px;margin-right:12px}.technical-evidence>.local-verification{margin-bottom:12px}
.state.ai-generated{background:#dff5ee;color:#087b66}.evidence-boundary{padding:10px 12px;border-radius:6px;background:#f6f9fa}
@media(max-width:700px){.origin-verdict{align-items:flex-start}.confidence{display:none}.credential-summary{grid-template-columns:1fr 1fr}.credential-summary div:nth-child(2){border-right:0}.credential-summary div:nth-child(-n+2){border-bottom:1px solid #e1e9ed}.technical-evidence>summary small{display:none}}
</style>
