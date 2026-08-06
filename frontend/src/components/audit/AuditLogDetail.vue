<template>
  <div v-if="event" class="drawer-mask" @click.self="$emit('close')">
    <aside class="detail-drawer" role="dialog" aria-modal="true" aria-labelledby="audit-detail-title">
      <header class="drawer-header">
        <div class="header-copy">
          <p>{{ isReviewWorkspace ? 'HUMAN REVIEW WORKSPACE' : 'EVENT FORENSICS' }}</p>
          <h2 id="audit-detail-title">{{ isReviewWorkspace ? '人工复核工作区' : '日志取证详情' }}</h2>
          <span v-if="isReviewWorkspace">文本护栏样本 · 请依据原始内容独立判断</span>
        </div>
        <div v-if="isReviewWorkspace" class="step-indicator" aria-label="复核流程">
          <span class="done">1 查看材料</span><i></i><span :class="{ done: evidence }">2 核对判定</span><i></i><span :class="{ done: selectedLabel }">3 提交结论</span>
        </div>
        <button class="icon-button" type="button" title="关闭" @click="$emit('close')"><X :size="18" /></button>
      </header>

      <div class="detail-scroll">
        <div v-if="isReviewWorkspace" class="review-brief">
          <div class="brief-icon"><ClipboardCheck :size="20" /></div>
          <div><strong>这次需要审核什么？</strong><p>判断用户输入与模型回复是否包含违法违规、攻击滥用、隐私泄露或其他红线风险。不要审核事件编号、哈希值或接口字段。</p></div>
          <span v-if="reviewItem?.claim_state === 'mine'" class="claim-badge"><UserRoundCheck :size="13" />已由你领取</span>
        </div>

        <section v-if="isReviewWorkspace" class="review-section material-section">
          <div class="section-heading">
            <div><span class="section-index">01</span><div><h3>待审原始材料</h3><p>以下内容来自加密证据库，查看行为已写入审计日志。</p></div></div>
            <span v-if="evidence?.encrypted_at_rest" class="secure-state"><LockKeyhole :size="13" />静态加密保存</span>
          </div>

          <div v-if="evidenceLoading" class="material-loading"><LoaderCircle :size="20" class="spin" /><span>正在解密并载入原始材料…</span></div>
          <div v-else-if="evidenceError" class="material-error"><TriangleAlert :size="18" /><div><strong>原始材料读取失败</strong><p>{{ evidenceError }}</p></div><button type="button" @click="revealEvidence">重新读取</button></div>
          <div v-else-if="!evidence" class="material-locked">
            <LockKeyhole :size="24" /><strong>原始材料尚未打开</strong><p>只有已登录审核员可以查看，访问动作会自动留痕。</p>
            <button type="button" @click="revealEvidence"><Eye :size="15" />查看原始材料</button>
          </div>
          <div v-else class="material-grid" :class="{ single: !evidence.response }">
            <article class="material-block">
              <div class="material-label"><MessageSquareText :size="15" /><strong>用户原始输入</strong><span>{{ textLength(evidence.prompt) }} 字</span></div>
              <div class="material-content">{{ evidence.prompt || '本次请求没有用户文本输入。' }}</div>
            </article>
            <article v-if="evidence.response" class="material-block response-block">
              <div class="material-label"><Bot :size="15" /><strong>模型原始输出</strong><span>{{ textLength(evidence.response) }} 字</span></div>
              <div class="material-content">{{ evidence.response }}</div>
              <div v-if="evidence.dangerous" class="quarantine-note"><ShieldX :size="14" />该输出曾被护栏判定为危险并隔离</div>
            </article>
            <article v-if="evidenceMediaUrl" class="material-block image-block">
              <div class="material-label"><ImageIcon :size="15" /><strong>原始图片</strong><span>受控证据</span></div>
              <img :src="evidenceMediaUrl" alt="待人工复核的原始图片" />
            </article>
          </div>
        </section>

        <section v-if="isReviewWorkspace" class="review-section judgement-section">
          <div class="section-heading">
            <div><span class="section-index">02</span><div><h3>机器判定参考</h3><p>机器结果仅供复核参考，最终以人工看到的原始内容为准。</p></div></div>
          </div>
          <div class="judgement-layout">
            <div class="risk-summary" :class="reviewItem?.primary_verdict">
              <span>主审核结论</span><strong>{{ verdictLabel[reviewItem?.primary_verdict || 'safe'] }}</strong>
              <div class="risk-score"><i :style="{ width: riskPercent }"></i></div>
              <small>风险分 {{ riskScoreText }}</small>
            </div>
            <div class="judgement-detail">
              <dl>
                <div><dt>命中风险</dt><dd>{{ readableCategories }}</dd></div>
                <div><dt>处置建议</dt><dd>{{ decisionAdvice }}</dd></div>
                <div><dt>影子模型</dt><dd>{{ shadowDecisionText }}</dd></div>
                <div><dt>判定说明</dt><dd>{{ event.summary }}</dd></div>
              </dl>
              <div v-if="reviewItem?.is_disagreement" class="disagreement-note"><GitCompareArrows :size="15" />两个模型结论不一致，请重点依据原始材料判断。</div>
            </div>
          </div>
        </section>

        <section v-if="isReviewWorkspace" class="review-section decision-section">
          <div class="section-heading">
            <div><span class="section-index">03</span><div><h3>提交人工结论</h3><p>选择一个结论，并用一句话说明你看到的关键依据。</p></div></div>
          </div>

          <div v-if="reviewItem?.review_label" class="review-complete">
            <BadgeCheck :size="22" /><div><strong>该样本已完成复核：{{ verdictLabel[reviewItem.review_label] }}</strong><p>{{ reviewItem.review_note || reasonLabel(reviewItem.reason_code) }} · {{ reviewItem.reviewer }} · {{ formatTime(reviewItem.reviewed_at || event.occurred_at) }}</p></div>
          </div>
          <template v-else>
            <div class="decision-options" role="radiogroup" aria-label="人工复核结论">
              <button v-for="choice in reviewChoices" :key="choice.value" type="button" :class="[choice.value, { active: selectedLabel === choice.value }]" role="radio" :aria-checked="selectedLabel === choice.value" @click="selectedLabel = choice.value">
                <component :is="choice.icon" :size="20" /><span><strong>{{ choice.label }}</strong><small>{{ choice.description }}</small></span><Check v-if="selectedLabel === choice.value" :size="17" />
              </button>
            </div>
            <label class="note-field">
              <span>判断依据 <b>必填</b><em>{{ reviewNote.length }} / 500</em></span>
              <textarea v-model="reviewNote" maxlength="500" rows="3" placeholder="例如：输入要求生成钓鱼邮件并规避检测，属于网络攻击滥用，应阻断。"></textarea>
            </label>
            <div class="submit-row">
              <p><Info :size="14" />提交后标签锁定，并自动领取下一条待审样本。</p>
              <button type="button" :disabled="!canSubmit || busy" @click="submitReview"><LoaderCircle v-if="busy" :size="16" class="spin" /><Send v-else :size="16" />{{ busy ? '正在提交' : '提交复核结论' }}</button>
            </div>
          </template>
        </section>

        <div v-if="!isReviewWorkspace" class="decision-strip" :class="event.severity">
          <span>{{ severityLabel[event.severity] }}</span><strong>{{ event.summary }}</strong><b>{{ outcomeLabel[event.outcome] }}</b>
        </div>

        <details class="forensics" :open="!isReviewWorkspace">
          <summary><FileCode2 :size="15" /><span>{{ isReviewWorkspace ? '技术取证信息（审核时通常无需查看）' : '事件与完整性证据' }}</span><ChevronDown :size="15" /></summary>
          <div class="forensics-body">
            <dl class="detail-grid">
              <div><dt>发生时间</dt><dd>{{ formatTime(event.occurred_at) }}</dd></div>
              <div><dt>样本类型</dt><dd>{{ event.event_type === 'guardrail.check' ? '大模型护栏文本审核' : event.event_type }}</dd></div>
              <div><dt>模块 / 动作</dt><dd>{{ event.module }} / {{ event.action }}</dd></div>
              <div><dt>来源 IP</dt><dd>{{ event.client_ip || '-' }}</dd></div>
              <div><dt>事件编号</dt><dd>{{ event.id }}</dd></div>
              <div><dt>状态 / 延迟</dt><dd>{{ event.status_code || '-' }} / {{ event.latency_ms ?? '-' }} ms</dd></div>
            </dl>
            <div class="hash-list">
              <div><span>CONTENT SHA-256</span><code>{{ event.content_hash || '无内容载荷' }}</code></div>
              <div><span>RECORD HASH</span><code>{{ event.record_hash }}</code></div>
              <div><span>PREVIOUS HASH</span><code>{{ event.prev_hash }}</code></div>
            </div>
            <details v-if="Object.keys(event.metadata || {}).length" class="raw-metadata"><summary>查看结构化元数据 JSON</summary><pre>{{ JSON.stringify(event.metadata, null, 2) }}</pre></details>
            <div v-if="!isReviewWorkspace && event.has_evidence" class="generic-evidence">
              <button v-if="!evidence" type="button" :disabled="evidenceLoading" @click="revealEvidence"><Eye :size="15" />{{ evidenceLoading ? '解密中' : '查看原始证据' }}</button>
              <div v-if="evidence" class="generic-raw"><label>原始输入</label><pre>{{ evidence.prompt || '-' }}</pre><label>模型输出</label><pre>{{ evidence.response || '-' }}</pre></div>
            </div>
          </div>
        </details>
      </div>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { BadgeCheck, Bot, Check, ChevronDown, CircleAlert, ClipboardCheck, Eye, FileCode2, GitCompareArrows, Image as ImageIcon, Info, LoaderCircle, LockKeyhole, MessageSquareText, Send, ShieldCheck, ShieldQuestion, ShieldX, TriangleAlert, UserRoundCheck, X } from 'lucide-vue-next'
import type { Component } from 'vue'
import type { AuditEvent } from '../../composables/useAuditLogs'
import type { ShadowReviewItem } from '../../composables/useDashboard'

type ReviewLabel = 'safe' | 'borderline' | 'unsafe'
interface RawEvidence { prompt?: string; response?: string; image_url?: string; thumbnail_url?: string; dangerous: boolean; encrypted_at_rest: boolean }

const props = defineProps<{ event: AuditEvent | null; reviewItem?: ShadowReviewItem | null; busy?: boolean }>()
const emit = defineEmits<{ close: []; evidenceRevealed: [eventId: string]; resolve: [eventId: string, reviewLabel: ReviewLabel, reviewNote: string] }>()
const evidence = ref<RawEvidence | null>(null)
const evidenceLoading = ref(false)
const evidenceError = ref('')
const selectedLabel = ref<ReviewLabel | ''>('')
const reviewNote = ref('')
const severityLabel = { info: '信息', warning: '关注', high: '高风险', critical: '严重' }
const outcomeLabel: Record<string, string> = { success: '成功', allowed: '放行', review: '复核', blocked: '阻断', denied: '拒绝', error: '异常' }
const verdictLabel: Record<ReviewLabel, string> = { safe: '安全，可放行', borderline: '存疑，需升级', unsafe: '危险，应阻断' }
const categoryNames: Record<string, string> = { jailbreak: '越狱攻击', prompt_injection: '提示词注入', cyber_abuse: '网络攻击滥用', weapons_violence: '武器与暴力', self_harm: '自伤风险', sexual_content: '色情内容', child_safety: '未成年人安全', personal_data: '隐私数据', illegal_activity: '违法活动', agent_security: 'Agent 安全', adult_content: '成人内容', weapon_display: '武器展示', graphic_violence: '暴力血腥', political_sensitive: '政治敏感', marketing_violation: '营销违规' }
const reviewChoices: Array<{ value: ReviewLabel; label: string; description: string; icon: Component }> = [
  { value: 'safe', label: '安全', description: '内容正常，可以放行', icon: ShieldCheck },
  { value: 'borderline', label: '存疑', description: '证据不足或需上级复核', icon: ShieldQuestion },
  { value: 'unsafe', label: '危险', description: '命中红线，应当阻断', icon: ShieldX },
]

const isReviewWorkspace = computed(() => Boolean(props.reviewItem))
const metadata = computed(() => props.event?.metadata || {})
const shadow = computed(() => (metadata.value.shadow_evaluation || {}) as Record<string, unknown>)
const readableCategories = computed(() => props.reviewItem?.categories?.length ? props.reviewItem.categories.map(item => categoryNames[item] || item).join('、') : '未命中明确分类')
const riskNumber = computed(() => Number(props.reviewItem?.risk_score || 0))
const riskPercent = computed(() => `${Math.max(0, Math.min(100, riskNumber.value <= 1 ? riskNumber.value * 100 : riskNumber.value))}%`)
const riskScoreText = computed(() => riskNumber.value <= 1 ? `${(riskNumber.value * 100).toFixed(1)} / 100` : `${riskNumber.value.toFixed(1)} / 100`)
const decisionAdvice = computed(() => ({ safe: '建议放行', borderline: '建议转人工复核', unsafe: '建议阻断并留存证据' } as Record<string, string>)[props.reviewItem?.primary_verdict || 'safe'])
const shadowDecisionText = computed(() => shadow.value.status === 'ok' || props.reviewItem?.shadow_status === 'ok' ? `${props.reviewItem?.shadow_decision === 'fail' ? '建议拦截' : '建议通过'}${props.reviewItem?.shadow_confidence != null ? `（置信度 ${(props.reviewItem.shadow_confidence * 100).toFixed(1)}%）` : ''}` : '本次未获得有效结果')
const canSubmit = computed(() => Boolean(evidence.value && selectedLabel.value && reviewNote.value.trim().length >= 4))
const evidenceMediaUrl = computed(() => {
  const value = evidence.value?.image_url || evidence.value?.thumbnail_url || ''
  return value.startsWith('/api/') ? value : ''
})

function textLength(value?: string) { return [...(value || '')].length }
function formatTime(value: string) { return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'medium', hour12: false }).format(new Date(value)) }
function reasonLabel(value?: string) { return ({ policy_ambiguous: '内容边界不清，已升级复核', shadow_false_positive: '影子模型误报', shadow_false_negative: '影子模型漏报', human_confirmed_safe: '人工确认安全', human_confirmed_borderline: '人工确认存疑', human_confirmed_unsafe: '人工确认危险', primary_false_positive: '主审核误报', primary_false_negative: '主审核漏报' } as Record<string, string>)[value || ''] || '已完成人工判断' }

async function revealEvidence() {
  if (!props.event || evidenceLoading.value) return
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

function submitReview() {
  if (!props.event || !selectedLabel.value || !canSubmit.value) return
  emit('resolve', props.event.id, selectedLabel.value, reviewNote.value.trim())
}

watch(() => props.event?.id, () => {
  evidence.value = null
  evidenceError.value = ''
  selectedLabel.value = ''
  reviewNote.value = ''
  if (props.event && props.reviewItem) void revealEvidence()
}, { immediate: true })
</script>

<style scoped>
.drawer-mask{position:fixed;inset:0;z-index:180;background:rgba(18,38,54,.42);backdrop-filter:blur(4px)}
.detail-drawer{width:min(1040px,100vw);height:100vh;margin-left:auto;display:flex;flex-direction:column;background:#f7f9fb;border-left:1px solid var(--line-bright);box-shadow:-24px 0 70px rgba(16,40,60,.22)}
.drawer-header{min-height:76px;display:flex;align-items:center;gap:24px;padding:14px 24px;background:#fff;border-bottom:1px solid var(--line)}.header-copy{min-width:210px}.header-copy p{margin:0 0 5px;color:var(--primary);font:700 9px/1 ui-monospace,monospace}.header-copy h2{margin:0;font-size:18px;letter-spacing:0}.header-copy span{display:block;margin-top:4px;color:var(--muted);font-size:10px}.icon-button{width:36px;height:36px;margin-left:auto;display:grid;place-items:center;color:var(--muted);background:transparent;border:1px solid var(--line);border-radius:6px;cursor:pointer}.icon-button:hover{color:var(--primary);background:var(--surface-3)}
.step-indicator{display:flex;align-items:center;gap:9px;color:var(--faint);font-size:10px}.step-indicator span{white-space:nowrap}.step-indicator span.done{color:var(--primary);font-weight:650}.step-indicator i{width:28px;height:1px;background:var(--line-bright)}
.detail-scroll{min-height:0;overflow:auto;padding:20px 24px 36px}.review-brief{display:flex;align-items:flex-start;gap:13px;padding:14px 16px;background:#edf6fa;border:1px solid #cce3ed;border-left:3px solid var(--primary);border-radius:6px}.brief-icon{width:34px;height:34px;flex:0 0 34px;display:grid;place-items:center;color:var(--primary);background:#fff;border:1px solid #cce3ed;border-radius:5px}.review-brief strong{font-size:12px}.review-brief p{margin:4px 0 0;max-width:680px;color:var(--muted);font-size:11px;line-height:1.65}.claim-badge,.secure-state{margin-left:auto;display:flex;align-items:center;gap:5px;white-space:nowrap;color:var(--success);font-size:10px;font-weight:650}
.review-section{margin-top:16px;padding:18px;background:#fff;border:1px solid var(--line);border-radius:7px;box-shadow:0 4px 16px rgba(28,52,70,.045)}.section-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:15px}.section-heading>div{display:flex;align-items:flex-start;gap:10px}.section-index{width:25px;height:25px;display:grid;place-items:center;color:#fff;background:var(--primary);border-radius:4px;font:700 9px ui-monospace,monospace}.section-heading h3{margin:0;font-size:13px}.section-heading p{margin:4px 0 0;color:var(--faint);font-size:10px;line-height:1.5}
.material-loading,.material-locked{min-height:170px;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:9px;color:var(--muted);background:#f8fafb;border:1px dashed var(--line-bright);border-radius:6px}.material-locked strong{color:var(--text);font-size:12px}.material-locked p{margin:0;color:var(--faint);font-size:10px}.material-locked button,.material-error button,.generic-evidence button{display:flex;align-items:center;gap:6px;min-height:34px;padding:0 12px;color:#fff;background:var(--primary);border:0;border-radius:5px;cursor:pointer}.material-error{display:flex;align-items:center;gap:12px;padding:15px;color:var(--danger);background:rgba(207,63,79,.05);border:1px solid rgba(207,63,79,.18);border-radius:6px}.material-error p{margin:3px 0 0;font-size:10px}.material-error button{margin-left:auto;background:var(--danger)}
.material-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.material-grid.single{grid-template-columns:1fr}.material-block{min-width:0;border:1px solid var(--line);border-radius:6px;overflow:hidden}.material-label{height:39px;display:flex;align-items:center;gap:7px;padding:0 12px;color:var(--primary);background:#f4f8fa;border-bottom:1px solid var(--line)}.material-label strong{color:var(--text);font-size:11px}.material-label span{margin-left:auto;color:var(--faint);font-size:9px}.material-content{min-height:150px;max-height:300px;overflow:auto;padding:14px;color:#253746;background:#fff;font-size:13px;line-height:1.75;white-space:pre-wrap;word-break:break-word}.response-block .material-label{color:#7356a8;background:#f7f5fa}.quarantine-note{display:flex;align-items:center;gap:6px;padding:8px 12px;color:var(--danger);background:rgba(207,63,79,.05);border-top:1px solid rgba(207,63,79,.15);font-size:9px}.image-block img{display:block;width:100%;max-height:360px;object-fit:contain;background:#eef2f5}
.judgement-layout{display:grid;grid-template-columns:220px 1fr;gap:14px}.risk-summary{padding:16px;background:#f5f8fa;border:1px solid var(--line);border-top:3px solid var(--primary);border-radius:5px}.risk-summary.unsafe{border-top-color:var(--danger)}.risk-summary.borderline{border-top-color:var(--warning)}.risk-summary span,.risk-summary small{display:block;color:var(--faint);font-size:9px}.risk-summary strong{display:block;margin:8px 0 16px;font-size:17px}.risk-summary.unsafe strong{color:var(--danger)}.risk-summary.borderline strong{color:var(--warning)}.risk-score{height:6px;margin-bottom:7px;overflow:hidden;background:#e5ebef;border-radius:2px}.risk-score i{display:block;height:100%;background:linear-gradient(90deg,var(--success),var(--warning) 58%,var(--danger))}.judgement-detail{padding:0 2px}.judgement-detail dl{display:grid;grid-template-columns:1fr 1fr;margin:0;border-top:1px solid var(--line);border-left:1px solid var(--line)}.judgement-detail dl div{padding:10px;border-right:1px solid var(--line);border-bottom:1px solid var(--line)}dt{margin-bottom:5px;color:var(--faint);font-size:9px}dd{margin:0;color:var(--text);font-size:11px;line-height:1.5;word-break:break-word}.disagreement-note{display:flex;align-items:center;gap:7px;margin-top:9px;padding:8px 10px;color:var(--warning);background:rgba(184,111,18,.06);border:1px solid rgba(184,111,18,.17);font-size:10px}
.decision-options{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.decision-options button{min-height:70px;display:flex;align-items:center;gap:10px;padding:12px;color:var(--muted);text-align:left;background:#fff;border:1px solid var(--line);border-radius:6px;cursor:pointer}.decision-options button>span{display:flex;flex:1;flex-direction:column;gap:4px}.decision-options strong{color:var(--text);font-size:12px}.decision-options small{color:var(--faint);font-size:9px}.decision-options button.safe:hover,.decision-options button.safe.active{color:var(--success);border-color:var(--success);background:rgba(22,128,94,.045)}.decision-options button.borderline:hover,.decision-options button.borderline.active{color:var(--warning);border-color:var(--warning);background:rgba(184,111,18,.045)}.decision-options button.unsafe:hover,.decision-options button.unsafe.active{color:var(--danger);border-color:var(--danger);background:rgba(207,63,79,.045)}.note-field{display:block;margin-top:14px}.note-field>span{display:flex;align-items:center;margin-bottom:7px;color:var(--muted);font-size:10px;font-weight:650}.note-field b{margin-left:6px;color:var(--danger);font-size:9px}.note-field em{margin-left:auto;color:var(--faint);font-style:normal;font-weight:400}.note-field textarea{width:100%;padding:11px 12px;resize:vertical;color:var(--text);background:#fbfcfd;border:1px solid var(--line);border-radius:6px;font:12px/1.65 inherit}.note-field textarea:focus{outline:none;border-color:var(--primary);box-shadow:0 0 0 3px rgba(8,126,174,.08)}.submit-row{display:flex;align-items:center;gap:16px;margin-top:12px}.submit-row p{display:flex;align-items:center;gap:6px;margin:0;color:var(--faint);font-size:9px}.submit-row button{min-width:150px;height:38px;margin-left:auto;display:flex;align-items:center;justify-content:center;gap:7px;color:#fff;background:var(--primary);border:0;border-radius:6px;font-size:11px;font-weight:650;cursor:pointer}.submit-row button:disabled{opacity:.42;cursor:not-allowed}.review-complete{display:flex;align-items:center;gap:11px;padding:15px;color:var(--success);background:rgba(22,128,94,.05);border:1px solid rgba(22,128,94,.2);border-radius:6px}.review-complete strong{font-size:12px}.review-complete p{margin:4px 0 0;color:var(--muted);font-size:10px}
.decision-strip{display:grid;grid-template-columns:70px 1fr auto;align-items:center;gap:12px;padding:13px 14px;border-left:3px solid var(--primary);background:#fff}.decision-strip span{color:var(--primary);font-size:10px;font-weight:700}.decision-strip strong{font-size:12px}.decision-strip b{font-size:11px}.decision-strip.warning{border-color:var(--warning)}.decision-strip.high,.decision-strip.critical{border-color:var(--danger)}
.forensics{margin-top:16px;background:#fff;border:1px solid var(--line);border-radius:6px}.forensics>summary{height:44px;display:flex;align-items:center;gap:8px;padding:0 14px;color:var(--muted);font-size:10px;font-weight:650;cursor:pointer;list-style:none}.forensics>summary svg:last-child{margin-left:auto;transition:transform .2s}.forensics[open]>summary svg:last-child{transform:rotate(180deg)}.forensics-body{padding:0 14px 14px;border-top:1px solid var(--line)}.detail-grid{display:grid;grid-template-columns:repeat(3,1fr);margin:14px 0;border-top:1px solid var(--line);border-left:1px solid var(--line)}.detail-grid div{min-width:0;padding:9px;border-right:1px solid var(--line);border-bottom:1px solid var(--line)}.hash-list div{padding:8px 10px;background:#f7f9fa;border:1px solid var(--line);border-bottom:0}.hash-list div:last-child{border-bottom:1px solid var(--line)}.hash-list span{display:block;margin-bottom:4px;color:var(--faint);font-size:8px}.hash-list code{display:block;color:var(--muted);font-size:9px;word-break:break-all}.raw-metadata{margin-top:12px}.raw-metadata summary{color:var(--muted);font-size:10px;cursor:pointer}.raw-metadata pre,.generic-raw pre{max-height:240px;overflow:auto;padding:11px;color:#cfe1ea;background:#10283c;border:1px solid #29485e;border-radius:5px;font:10px/1.6 ui-monospace,monospace;white-space:pre-wrap;word-break:break-word}.generic-evidence{margin-top:13px}.generic-raw label{display:block;margin:11px 0 5px;color:var(--muted);font-size:10px}.spin{animation:spin .85s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
@media(max-width:760px){.drawer-header{align-items:flex-start}.step-indicator{display:none}.detail-scroll{padding:14px}.review-brief{flex-wrap:wrap}.claim-badge{width:100%;margin-left:47px}.material-grid,.judgement-layout,.decision-options{grid-template-columns:1fr}.judgement-detail dl,.detail-grid{grid-template-columns:1fr}.submit-row{align-items:stretch;flex-direction:column}.submit-row button{width:100%;margin-left:0}}
</style>
