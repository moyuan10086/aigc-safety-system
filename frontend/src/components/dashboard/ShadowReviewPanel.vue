<template>
  <div class="shadow-review">
    <div class="shadow-metrics">
      <div :class="{ success: summary.target_completed }"><span>有效标签进度</span><strong>{{ summary.verified_review_count }} / {{ summary.target_labels }}</strong><small>{{ summary.review_completion_rate }}% · 还需 {{ summary.remaining_count }} 条</small></div>
      <div :class="{ success: summary.pilot_completed, danger: summary.unverified_review_count > 0 }"><span>首批有效试标</span><strong>{{ Math.min(summary.verified_review_count, summary.pilot_target_labels) }} / {{ summary.pilot_target_labels }}</strong><small>{{ pilotStatus }}</small></div>
      <div :class="{ success: summary.reviewed_count > 0 && summary.review_integrity_complete, danger: summary.unverified_review_count > 0 }"><span>标签完整性</span><strong>{{ summary.verified_review_count }} / {{ summary.reviewed_count }}</strong><small>{{ integrityStatus }}</small></div>
      <div><span>我的复核</span><strong>{{ summary.reviewer_reviewed_count }}</strong><small>已领取 {{ summary.claimed_by_me_count }} 条</small></div>
      <div><span>可复核样本</span><strong>{{ summary.eligible_samples }}</strong><small>待复核 {{ summary.pending_reviews }} 条</small></div>
      <div class="danger"><span>模型分歧</span><strong>{{ summary.disagreement_count }}</strong><small>队列优先展示分歧</small></div>
      <div><span>活跃领取</span><strong>{{ summary.active_claims }}</strong><small>15 分钟无操作自动释放</small></div>
    </div>
    <div class="progress-track" role="progressbar" :aria-valuenow="summary.verified_review_count" aria-valuemin="0" :aria-valuemax="summary.target_labels">
      <i :style="{ width: `${progress}%` }"></i>
    </div>
    <ol class="review-guide" aria-label="人工试标操作步骤">
      <li><b>1</b><span>领取样本</span><small>点击“开始复核”，获得 15 分钟独占租约</small></li>
      <li><b>2</b><span>查看加密证据</span><small>在取证详情中查看原始提示词与模型输出，访问动作自动留痕</small></li>
      <li><b>3</b><span>提交首次标签</span><small>选择安全、边界或危险；标签锁定后自动领取下一条</small></li>
    </ol>
    <div v-if="summary.unverified_review_count" class="integrity-alert" role="alert">
      <CircleAlert :size="16" /><span>检测到 {{ summary.unverified_review_count }} 条标签缺少领取或证据访问审计，试标里程碑不会被标记为完成，请先核查审计记录。</span>
    </div>
    <div v-if="summary.reviewed_count" class="review-summary" aria-label="人工标签质量摘要">
      <span>标签分布</span>
      <b class="safe">安全 {{ summary.review_labels.safe || 0 }}</b>
      <b class="borderline">边界 {{ summary.review_labels.borderline || 0 }}</b>
      <b class="unsafe">危险 {{ summary.review_labels.unsafe || 0 }}</b>
      <i></i>
      <span>审核员贡献</span>
      <b v-for="reviewer in summary.reviewer_counts.slice(0, 5)" :key="reviewer.reviewer">{{ reviewer.reviewer }} {{ reviewer.count }}</b>
    </div>

    <div class="queue-head">
      <div><strong>人工复核样本池</strong><span>{{ blindMode ? '盲审开启 · 模型结论已隐藏' : '模型对照 · 仅用于复核分析' }}</span></div>
      <div class="review-mode" role="group" aria-label="复核显示模式">
        <button type="button" :class="{ active: blindMode }" title="隐藏模型判定，先独立给出人工真值" @click="blindMode = true"><EyeOff :size="13" />盲审</button>
        <button type="button" :class="{ active: !blindMode }" title="显示主判与影子模型结果" @click="blindMode = false"><GitCompareArrows :size="13" />对照</button>
      </div>
      <a href="/api/dashboard/review-labels.csv" title="导出不含原始提示词和输出的标签元数据"><Download :size="14" />导出标签</a>
    </div>
    <div v-if="items.length" class="review-list">
      <article v-for="item in items" :key="item.event_id" class="review-row" :class="{ locked: item.claim_state === 'other' }">
        <div class="event-meta">
          <time>{{ formatTime(item.occurred_at) }}</time>
          <code>{{ item.content_hash?.slice(0, 12) || item.event_id.slice(0, 12) }}</code>
          <button type="button" :class="{ reviewed: item.evidence_reviewed, claimed: item.claim_state === 'mine', locked: item.claim_state === 'other' }" :disabled="busyEventId === item.event_id || item.claim_state === 'other'" :title="inspectTitle(item)" @click="$emit('inspect', item.event_id, !item.review_label)">
            <component :is="inspectIcon(item)" :size="15" /><span>{{ inspectLabel(item) }}</span>
          </button>
        </div>
        <div v-if="revealModel(item)" class="decision-pair">
          <span>主判 <b :class="item.primary_verdict">{{ verdictLabel[item.primary_verdict] }}</b></span>
          <ArrowRight :size="14" />
          <span v-if="item.shadow_decision">影子 <b :class="item.shadow_decision">{{ shadowLabel[item.shadow_decision] }}</b></span>
          <span v-else>影子 <b>未启用</b></span>
          <em v-if="item.is_disagreement">分歧优先</em>
        </div>
        <div v-else class="decision-pair blind-result"><EyeOff :size="14" /><span>模型判定已隐藏</span></div>
        <div v-if="revealModel(item)" class="model-meta">
          <span>{{ item.risk_code || 'GR-UNKNOWN' }}</span>
          <span>置信 {{ percent(item.shadow_confidence) }}</span>
          <span>{{ item.shadow_latency_ms ?? '-' }} ms</span>
        </div>
        <div v-else class="model-meta blind-result"><span>人工真值优先</span></div>
        <div class="review-control" :class="{ complete: item.review_label }">
          <template v-if="item.review_label"><BadgeCheck :size="14" /><span>人工结论：{{ verdictLabel[item.review_label] }}</span></template>
          <template v-else><ClipboardCheck :size="14" /><span>请在工作区查看原文并提交结论</span></template>
        </div>
      </article>
    </div>
    <div v-else class="empty-state"><BadgeCheck :size="22" /><span>暂无含加密证据的待复核样本</span></div>
  </div>
</template>

<script setup lang="ts">
import { ArrowRight, BadgeCheck, CircleAlert, ClipboardCheck, Download, EyeOff, FileSearch, GitCompareArrows, LockKeyhole } from 'lucide-vue-next'
import { computed, ref } from 'vue'
import type { ShadowEvaluationSummary, ShadowReviewItem } from '../../composables/useDashboard'

const props = defineProps<{ summary: ShadowEvaluationSummary; items: ShadowReviewItem[]; busyEventId: string }>()
defineEmits<{
  inspect: [eventId: string, shouldClaim: boolean]
}>()

const verdictLabel = { safe: '安全', borderline: '边界', unsafe: '危险' }
const shadowLabel = { pass: '通过', fail: '拦截' }
const blindMode = ref(true)
const progress = computed(() => props.summary.target_labels ? Math.min(100, props.summary.verified_review_count / props.summary.target_labels * 100) : 0)
const pilotStatus = computed(() => {
  if (props.summary.unverified_review_count) return `完整性异常 ${props.summary.unverified_review_count} 条`
  return props.summary.pilot_completed ? '双审计完整，试标里程碑已完成' : `还需 ${props.summary.pilot_remaining_count} 条有效标签`
})
const integrityStatus = computed(() => {
  if (!props.summary.reviewed_count) return '尚无人工标签'
  return props.summary.review_integrity_complete ? '领取与证据访问审计完整' : `异常 ${props.summary.unverified_review_count} 条`
})
const timeFormatter = new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })
function formatTime(value: string) { return timeFormatter.format(new Date(value)) }
function percent(value?: number) { return value == null ? '-' : `${(value * 100).toFixed(1)}%` }
function revealModel(item: ShadowReviewItem) { return !blindMode.value || Boolean(item.review_label) }
function inspectIcon(item: ShadowReviewItem) { return item.review_label || item.evidence_reviewed ? BadgeCheck : item.claim_state === 'other' ? LockKeyhole : FileSearch }
function inspectLabel(item: ShadowReviewItem) {
  if (item.review_label) return '已复核'
  if (item.claim_state === 'other') return '他人复核中'
  if (item.evidence_reviewed) return '已看证据'
  if (item.claim_state === 'mine') return '继续复核'
  return '开始复核'
}
function inspectTitle(item: ShadowReviewItem) {
  if (item.review_label) return '标签已锁定，可再次打开核对证据'
  if (item.claim_state === 'other') return '该样本正在由其他审核员复核'
  if (item.claim_state === 'mine') return '继续查看审计事件与加密证据'
  return '领取样本并查看审计事件'
}
</script>

<style scoped>
.shadow-review{min-height:0}.shadow-metrics{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));border-bottom:1px solid var(--line)}.shadow-metrics>div{min-width:0;padding:13px 16px;border-right:1px solid var(--line)}.shadow-metrics>div:last-child{border-right:0}.shadow-metrics span,.shadow-metrics small{display:block;color:var(--faint);font-size:9px}.shadow-metrics strong{display:block;margin:5px 0 4px;color:var(--text);font:700 20px/1 ui-monospace,monospace}.shadow-metrics .danger strong{color:var(--danger)}.shadow-metrics .success strong{color:var(--success)}
.progress-track{height:3px;background:var(--surface-3)}.progress-track i{display:block;height:100%;background:var(--primary);transition:width .25s ease}
.review-guide{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));margin:0;padding:10px 16px;list-style:none;background:var(--surface);border-bottom:1px solid var(--line)}.review-guide li{min-width:0;display:grid;grid-template-columns:24px 1fr;column-gap:8px;padding:2px 14px;border-right:1px solid var(--line)}.review-guide li:first-child{padding-left:0}.review-guide li:last-child{padding-right:0;border-right:0}.review-guide b{grid-row:1/3;width:22px;height:22px;display:grid;place-items:center;color:#fff;background:var(--primary);border-radius:50%;font:700 9px/1 ui-monospace,monospace}.review-guide span{color:var(--text);font-size:10px;font-weight:650}.review-guide small{margin-top:3px;color:var(--faint);font-size:9px;line-height:1.45}.integrity-alert{display:flex;align-items:center;gap:8px;padding:8px 16px;color:var(--danger);background:rgba(207,63,79,.06);border-bottom:1px solid rgba(207,63,79,.16);font-size:9px}
.review-summary{min-height:34px;display:flex;align-items:center;gap:7px;padding:5px 16px;color:var(--faint);background:var(--surface-2);border-bottom:1px solid var(--line);font-size:9px}.review-summary b{padding:3px 6px;color:var(--muted);background:var(--surface-3);border-radius:4px;font-weight:650}.review-summary b.safe{color:var(--success)}.review-summary b.borderline{color:var(--warning)}.review-summary b.unsafe{color:var(--danger)}.review-summary i{width:1px;height:16px;margin:0 4px;background:var(--line)}
.queue-head{min-height:48px;display:flex;align-items:center;gap:12px;padding:7px 16px;background:var(--surface-2);border-bottom:1px solid var(--line)}.queue-head>div:first-child{min-width:0;display:flex;align-items:baseline;gap:10px}.queue-head strong{font-size:11px}.queue-head span{color:var(--faint);font-size:9px}.queue-head>span{margin-left:auto;color:var(--muted)}
.review-mode{height:28px;margin-left:auto;display:grid;grid-template-columns:repeat(2,76px);padding:2px;background:var(--surface-3);border:1px solid var(--line);border-radius:6px}.review-mode button{display:flex;align-items:center;justify-content:center;gap:5px;color:var(--muted);background:transparent;border:0;border-radius:4px;font-size:9px;cursor:pointer}.review-mode button.active{color:#fff;background:var(--primary);font-weight:650}.queue-head a{height:28px;display:flex;align-items:center;gap:6px;padding:0 9px;color:var(--primary);border:1px solid var(--line);border-radius:5px;font-size:9px;text-decoration:none}.queue-head a:hover{background:var(--surface);border-color:var(--line-bright)}
.review-list{max-height:310px;overflow:auto}.review-row{min-height:62px;display:grid;grid-template-columns:minmax(190px,.9fr) minmax(220px,1fr) minmax(190px,.9fr) 246px;align-items:center;gap:14px;padding:8px 16px;border-bottom:1px solid var(--line)}.review-row.locked{background:var(--surface-2)}.review-row:last-child{border-bottom:0}.event-meta,.decision-pair,.model-meta{min-width:0;display:flex;align-items:center;gap:8px}.event-meta time{color:var(--muted);font-size:9px}.event-meta code{overflow:hidden;color:var(--faint);font-size:9px;text-overflow:ellipsis}.event-meta button{height:28px;margin-left:auto;display:flex;align-items:center;gap:5px;padding:0 8px;color:var(--primary);background:transparent;border:1px solid var(--line);border-radius:5px;font-size:9px;cursor:pointer}.event-meta button:hover:not(:disabled){background:var(--surface-3);border-color:var(--line-bright)}.event-meta button:disabled{cursor:not-allowed;opacity:.7}.event-meta button.claimed{color:var(--warning);border-color:rgba(184,111,18,.25)}.event-meta button.locked{color:var(--muted)}.event-meta button.reviewed{color:var(--success);border-color:rgba(22,128,94,.25);background:rgba(22,128,94,.05)}
.decision-pair{justify-content:center;color:var(--faint)}.decision-pair span{font-size:9px}.decision-pair b{margin-left:4px;padding:3px 6px;color:var(--muted);background:var(--surface-3);border-radius:3px;font-size:9px}.decision-pair b.safe,.decision-pair b.pass{color:var(--success);background:rgba(22,128,94,.09)}.decision-pair b.borderline{color:var(--warning);background:rgba(184,111,18,.09)}.decision-pair b.unsafe,.decision-pair b.fail{color:var(--danger);background:rgba(207,63,79,.08)}
.decision-pair em{padding:3px 5px;color:var(--danger);background:rgba(207,63,79,.08);border:1px solid rgba(207,63,79,.16);border-radius:3px;font-size:8px;font-style:normal}
.blind-result{color:var(--muted)}.decision-pair.blind-result{gap:6px}.model-meta{justify-content:flex-end}.model-meta span{padding-right:8px;color:var(--faint);border-right:1px solid var(--line);font:9px/1 ui-monospace,monospace}.model-meta span:last-child{padding-right:0;border-right:0}.review-control{height:31px;display:flex;align-items:center;justify-content:center;gap:6px;padding:0 9px;color:var(--muted);background:var(--surface-2);border:1px solid var(--line);border-radius:6px;font-size:9px}.review-control.complete{color:var(--success);background:rgba(22,128,94,.05);border-color:rgba(22,128,94,.2)}.empty-state{height:150px;display:flex;align-items:center;justify-content:center;gap:8px;color:var(--faint);font-size:10px}
@media(max-width:1380px){.shadow-metrics{grid-template-columns:repeat(4,1fr)}}@media(max-width:1200px){.shadow-metrics{grid-template-columns:repeat(3,1fr)}.review-row{grid-template-columns:1fr 1fr}.review-control{width:246px;justify-self:end}}@media(max-width:720px){.shadow-metrics{grid-template-columns:1fr 1fr}.shadow-metrics>div:nth-child(2n){border-right:0}.review-guide{grid-template-columns:1fr;gap:9px}.review-guide li,.review-guide li:first-child,.review-guide li:last-child{padding:0;border-right:0}.review-summary{align-items:flex-start;flex-wrap:wrap}.review-summary i{display:none}.review-summary span:nth-of-type(2){width:100%;margin-top:2px}.review-row{grid-template-columns:1fr}.decision-pair{justify-content:flex-start}.model-meta{justify-content:flex-start}.review-control{width:100%;justify-self:stretch}.queue-head{align-items:stretch;flex-wrap:wrap}.queue-head>div:first-child{width:100%}.queue-head>div:first-child span{display:none}.review-mode{margin-left:0;flex:1;grid-template-columns:repeat(2,minmax(64px,1fr))}.queue-head a{justify-content:center}}
</style>
