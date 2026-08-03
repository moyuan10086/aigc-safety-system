<template>
  <div class="shadow-review">
    <div class="shadow-metrics">
      <div><span>可比样本</span><strong>{{ summary.evaluated_samples }}</strong><small>观察 {{ summary.observed_events }} 条</small></div>
      <div><span>一致率</span><strong>{{ summary.agreement_rate }}%</strong><small>{{ summary.agreement_count }} 一致 / {{ summary.disagreement_count }} 分歧</small></div>
      <div class="danger"><span>待复核</span><strong>{{ summary.pending_reviews }}</strong><small>误报候选 {{ summary.false_positive_candidates }}</small></div>
      <div><span>影子 P95</span><strong>{{ summary.p95_latency_ms }} ms</strong><small>仅统计成功推理</small></div>
    </div>

    <div class="queue-head">
      <div><strong>最近分歧队列</strong><span>仅展示结构化指标；点击取证后才解密原文</span></div>
      <span>{{ summary.reviewed_count }} 已复核</span>
    </div>
    <div v-if="items.length" class="review-list">
      <article v-for="item in items" :key="item.event_id" class="review-row">
        <div class="event-meta">
          <time>{{ formatTime(item.occurred_at) }}</time>
          <code>{{ item.content_hash?.slice(0, 12) || item.event_id.slice(0, 12) }}</code>
          <button type="button" :title="item.has_evidence ? '查看审计事件与加密证据' : '查看审计事件'" @click="$emit('inspect', item.event_id)">
            <FileSearch :size="15" /><span>取证</span>
          </button>
        </div>
        <div class="decision-pair">
          <span>主判 <b :class="item.primary_verdict">{{ verdictLabel[item.primary_verdict] }}</b></span>
          <ArrowRight :size="14" />
          <span>影子 <b :class="item.shadow_decision">{{ shadowLabel[item.shadow_decision] }}</b></span>
        </div>
        <div class="model-meta">
          <span>{{ item.risk_code || 'GR-UNKNOWN' }}</span>
          <span>置信 {{ percent(item.shadow_confidence) }}</span>
          <span>{{ item.shadow_latency_ms ?? '-' }} ms</span>
        </div>
        <div class="review-control" role="group" :aria-label="`${item.event_id} 人工复核标签`">
          <button v-for="choice in choices" :key="choice.value" type="button" :class="[choice.value, { active: item.review_label === choice.value }]" :disabled="busyEventId === item.event_id" :title="choice.title" @click="$emit('resolve', item.event_id, choice.value)">
            <component :is="choice.icon" :size="14" />{{ choice.label }}
          </button>
        </div>
      </article>
    </div>
    <div v-else class="empty-state"><BadgeCheck :size="22" /><span>当前窗口没有主判与影子模型分歧</span></div>
  </div>
</template>

<script setup lang="ts">
import { ArrowRight, BadgeCheck, CircleAlert, FileSearch, ShieldCheck, ShieldX } from 'lucide-vue-next'
import type { Component } from 'vue'
import type { ShadowEvaluationSummary, ShadowReviewItem } from '../../composables/useDashboard'

defineProps<{ summary: ShadowEvaluationSummary; items: ShadowReviewItem[]; busyEventId: string }>()
defineEmits<{
  resolve: [eventId: string, reviewLabel: 'safe' | 'borderline' | 'unsafe']
  inspect: [eventId: string]
}>()

const verdictLabel = { safe: '安全', borderline: '边界', unsafe: '危险' }
const shadowLabel = { pass: '通过', fail: '拦截' }
const choices: Array<{ value: 'safe' | 'borderline' | 'unsafe'; label: string; title: string; icon: Component }> = [
  { value: 'safe', label: '安全', title: '人工确认该样本应安全放行', icon: ShieldCheck },
  { value: 'borderline', label: '边界', title: '人工确认该样本需要进一步复核', icon: CircleAlert },
  { value: 'unsafe', label: '危险', title: '人工确认该样本应阻断', icon: ShieldX },
]
const timeFormatter = new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })
function formatTime(value: string) { return timeFormatter.format(new Date(value)) }
function percent(value?: number) { return value == null ? '-' : `${(value * 100).toFixed(1)}%` }
</script>

<style scoped>
.shadow-review{min-height:0}.shadow-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border-bottom:1px solid var(--line)}.shadow-metrics>div{min-width:0;padding:13px 16px;border-right:1px solid var(--line)}.shadow-metrics>div:last-child{border-right:0}.shadow-metrics span,.shadow-metrics small{display:block;color:var(--faint);font-size:9px}.shadow-metrics strong{display:block;margin:5px 0 4px;color:var(--text);font:700 20px/1 ui-monospace,monospace}.shadow-metrics .danger strong{color:var(--danger)}
.queue-head{height:48px;display:flex;align-items:center;gap:12px;padding:0 16px;background:var(--surface-2);border-bottom:1px solid var(--line)}.queue-head>div{min-width:0;display:flex;align-items:baseline;gap:10px}.queue-head strong{font-size:11px}.queue-head span{color:var(--faint);font-size:9px}.queue-head>span{margin-left:auto;color:var(--muted)}
.review-list{max-height:310px;overflow:auto}.review-row{min-height:62px;display:grid;grid-template-columns:minmax(190px,.9fr) minmax(220px,1fr) minmax(190px,.9fr) 246px;align-items:center;gap:14px;padding:8px 16px;border-bottom:1px solid var(--line)}.review-row:last-child{border-bottom:0}.event-meta,.decision-pair,.model-meta{min-width:0;display:flex;align-items:center;gap:8px}.event-meta time{color:var(--muted);font-size:9px}.event-meta code{overflow:hidden;color:var(--faint);font-size:9px;text-overflow:ellipsis}.event-meta button{height:28px;margin-left:auto;display:flex;align-items:center;gap:5px;padding:0 8px;color:var(--primary);background:transparent;border:1px solid var(--line);border-radius:5px;font-size:9px;cursor:pointer}.event-meta button:hover{background:var(--surface-3);border-color:var(--line-bright)}
.decision-pair{justify-content:center;color:var(--faint)}.decision-pair span{font-size:9px}.decision-pair b{margin-left:4px;padding:3px 6px;color:var(--muted);background:var(--surface-3);border-radius:3px;font-size:9px}.decision-pair b.safe,.decision-pair b.pass{color:var(--success);background:rgba(22,128,94,.09)}.decision-pair b.borderline{color:var(--warning);background:rgba(184,111,18,.09)}.decision-pair b.unsafe,.decision-pair b.fail{color:var(--danger);background:rgba(207,63,79,.08)}
.model-meta{justify-content:flex-end}.model-meta span{padding-right:8px;color:var(--faint);border-right:1px solid var(--line);font:9px/1 ui-monospace,monospace}.model-meta span:last-child{padding-right:0;border-right:0}.review-control{height:31px;display:grid;grid-template-columns:repeat(3,1fr);padding:2px;background:var(--surface-3);border:1px solid var(--line);border-radius:6px}.review-control button{display:flex;align-items:center;justify-content:center;gap:5px;color:var(--muted);background:transparent;border:0;border-radius:4px;font-size:9px;cursor:pointer}.review-control button:hover:not(:disabled){color:var(--primary);background:var(--surface)}.review-control button.active{color:#fff;background:var(--primary);font-weight:650}.review-control button.active.safe{background:var(--success)}.review-control button.active.borderline{background:var(--warning)}.review-control button.active.unsafe{background:var(--danger)}.review-control button:disabled{opacity:.55;cursor:wait}.empty-state{height:150px;display:flex;align-items:center;justify-content:center;gap:8px;color:var(--faint);font-size:10px}
@media(max-width:1200px){.review-row{grid-template-columns:1fr 1fr}.review-control{width:246px;justify-self:end}}@media(max-width:720px){.shadow-metrics{grid-template-columns:1fr 1fr}.shadow-metrics>div:nth-child(2){border-right:0}.review-row{grid-template-columns:1fr}.decision-pair{justify-content:flex-start}.model-meta{justify-content:flex-start}.review-control{width:100%;justify-self:stretch}.queue-head>div span{display:none}}
</style>
