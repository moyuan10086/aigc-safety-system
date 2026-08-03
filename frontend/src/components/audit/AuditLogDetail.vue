<template>
  <div v-if="event" class="drawer-mask" @click.self="$emit('close')">
    <aside class="detail-drawer" role="dialog" aria-modal="true" aria-labelledby="audit-detail-title">
      <header>
        <div><p>EVENT FORENSICS</p><h2 id="audit-detail-title">日志取证详情</h2></div>
        <button class="icon-button" type="button" title="关闭" @click="$emit('close')"><X :size="18" /></button>
      </header>

      <div class="detail-scroll">
        <div class="decision-strip" :class="event.severity">
          <span>{{ severityLabel[event.severity] }}</span><strong>{{ event.summary }}</strong><b>{{ outcomeLabel[event.outcome] }}</b>
        </div>

        <section>
          <h3>事件信息</h3>
          <dl class="detail-grid">
            <div><dt>发生时间</dt><dd>{{ formatTime(event.occurred_at) }}</dd></div>
            <div><dt>事件类型</dt><dd>{{ event.event_type }}</dd></div>
            <div><dt>模块 / 动作</dt><dd>{{ event.module }} / {{ event.action }}</dd></div>
            <div><dt>操作者</dt><dd>{{ event.actor || '-' }}</dd></div>
            <div><dt>来源 IP</dt><dd>{{ event.client_ip || '-' }}</dd></div>
            <div><dt>状态 / 延迟</dt><dd>{{ event.status_code || '-' }} / {{ event.latency_ms ?? '-' }} ms</dd></div>
            <div v-if="event.risk_code"><dt>风险代码</dt><dd>{{ event.risk_code }} · {{ event.risk_score ?? '-' }}</dd></div>
            <div v-if="event.path"><dt>请求路径</dt><dd>{{ event.method }} {{ event.path }}</dd></div>
          </dl>
        </section>

        <section>
          <h3>完整性证据</h3>
          <div class="hash-block"><span>CONTENT SHA-256</span><code>{{ event.content_hash || '无内容载荷' }}</code></div>
          <div class="hash-block"><span>RECORD HASH</span><code>{{ event.record_hash }}</code></div>
          <div class="hash-block"><span>PREVIOUS HASH</span><code>{{ event.prev_hash }}</code></div>
        </section>

        <section v-if="Object.keys(event.metadata || {}).length">
          <h3>结构化元数据</h3><pre>{{ JSON.stringify(event.metadata, null, 2) }}</pre>
        </section>

        <section v-if="event.has_evidence" class="evidence-vault">
          <div class="vault-head">
            <div><h3>隔离证据库</h3><p>AES-GCM 加密保存 · 查看行为将被审计</p></div>
            <button v-if="!evidence" type="button" :disabled="evidenceLoading" @click="revealEvidence"><Eye :size="15" />{{ evidenceLoading ? '解密中' : '查看原始证据' }}</button>
          </div>
          <p v-if="evidenceError" class="error-text">{{ evidenceError }}</p>
          <div v-if="evidence" class="raw-evidence">
            <div v-if="evidence.dangerous" class="danger-note"><TriangleAlert :size="15" />该内容曾被安全护栏阻断或隔离</div>
            <label v-if="evidence.prompt">原始提示词</label><pre v-if="evidence.prompt">{{ evidence.prompt }}</pre>
            <label v-if="evidence.response">模型原始输出</label><pre v-if="evidence.response">{{ evidence.response }}</pre>
          </div>
        </section>
      </div>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Eye, TriangleAlert, X } from 'lucide-vue-next'
import type { AuditEvent } from '../../composables/useAuditLogs'

const props = defineProps<{ event: AuditEvent | null }>()
const emit = defineEmits<{ close: []; evidenceRevealed: [eventId: string] }>()
const evidence = ref<any>(null)
const evidenceLoading = ref(false)
const evidenceError = ref('')
const severityLabel = { info: '信息', warning: '关注', high: '高风险', critical: '严重' }
const outcomeLabel: Record<string, string> = { success: '成功', allowed: '放行', review: '复核', blocked: '阻断', denied: '拒绝', error: '异常' }

function formatTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'medium', hour12: false }).format(new Date(value))
}

async function revealEvidence() {
  if (!props.event) return
  evidenceLoading.value = true
  evidenceError.value = ''
  try {
    const response = await fetch(`/api/audit/logs/${props.event.id}/evidence`, { credentials: 'same-origin' })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.detail || '原始证据读取失败')
    evidence.value = data
    emit('evidenceRevealed', props.event.id)
  } catch (caught) {
    evidenceError.value = (caught as Error).message
  } finally {
    evidenceLoading.value = false
  }
}

watch(() => props.event?.id, () => { evidence.value = null; evidenceError.value = '' })
</script>

<style scoped>
.drawer-mask{position:fixed;inset:0;z-index:180;background:rgba(16,40,60,.34);backdrop-filter:blur(3px)}
.detail-drawer{width:min(620px,100vw);height:100vh;margin-left:auto;display:flex;flex-direction:column;background:var(--surface);border-left:1px solid var(--line-bright);box-shadow:-20px 0 60px rgba(16,40,60,.18)}
header{height:70px;flex:0 0 70px;display:flex;align-items:center;padding:0 22px;border-bottom:1px solid var(--line)}header p{margin:0 0 5px;color:var(--primary);font:700 9px/1 ui-monospace,monospace}header h2{margin:0;font-size:16px}.icon-button{width:34px;height:34px;margin-left:auto;display:grid;place-items:center;color:var(--muted);background:transparent;border:1px solid var(--line);border-radius:6px;cursor:pointer}.icon-button:hover{color:var(--primary);background:var(--surface-3)}
.detail-scroll{min-height:0;overflow:auto;padding:20px 22px 32px}.decision-strip{display:grid;grid-template-columns:70px 1fr auto;align-items:center;gap:12px;padding:13px 14px;border-left:3px solid var(--primary);background:var(--surface-2)}.decision-strip span{color:var(--primary);font-size:10px;font-weight:700}.decision-strip strong{font-size:12px;font-weight:600}.decision-strip b{font-size:11px}.decision-strip.warning{border-color:var(--warning)}.decision-strip.warning span{color:var(--warning)}.decision-strip.high,.decision-strip.critical{border-color:var(--danger)}.decision-strip.high span,.decision-strip.critical span{color:var(--danger)}
section{margin-top:22px}section h3{margin:0 0 10px;font-size:12px}.detail-grid{display:grid;grid-template-columns:1fr 1fr;margin:0;border-top:1px solid var(--line);border-left:1px solid var(--line)}.detail-grid div{min-width:0;padding:10px;border-right:1px solid var(--line);border-bottom:1px solid var(--line)}dt{margin-bottom:5px;color:var(--faint);font-size:9px}dd{margin:0;color:var(--text);font-size:11px;word-break:break-word}
.hash-block{padding:9px 10px;border:1px solid var(--line);border-bottom:0;background:var(--surface-2)}.hash-block:last-child{border-bottom:1px solid var(--line)}.hash-block span{display:block;margin-bottom:5px;color:var(--faint);font-size:8px}.hash-block code{display:block;color:var(--muted);font-size:9px;word-break:break-all}pre{max-height:260px;margin:0;padding:12px;overflow:auto;color:#cfe1ea;background:#10283c;border:1px solid #29485e;border-radius:6px;font:10px/1.65 ui-monospace,monospace;white-space:pre-wrap;word-break:break-word}
.evidence-vault{padding:14px;border:1px solid rgba(184,111,18,.28);background:rgba(184,111,18,.045);border-radius:7px}.vault-head{display:flex;align-items:center;gap:12px}.vault-head h3{margin-bottom:4px}.vault-head p{margin:0;color:var(--faint);font-size:9px}.vault-head button{min-height:34px;margin-left:auto;display:flex;align-items:center;gap:6px;padding:0 11px;color:#fff;background:var(--warning);border:0;border-radius:5px;font-size:10px;font-weight:650;cursor:pointer}.vault-head button:disabled{opacity:.55}.raw-evidence{margin-top:13px}.raw-evidence label{display:block;margin:12px 0 6px;color:var(--muted);font-size:10px;font-weight:650}.danger-note{display:flex;align-items:center;gap:7px;padding:8px 10px;color:var(--danger);background:rgba(207,63,79,.08);border:1px solid rgba(207,63,79,.2);font-size:10px}.error-text{color:var(--danger);font-size:10px}
@media(max-width:600px){.detail-grid{grid-template-columns:1fr}.decision-strip{grid-template-columns:1fr}.vault-head{align-items:flex-start;flex-direction:column}.vault-head button{margin-left:0}}
</style>
