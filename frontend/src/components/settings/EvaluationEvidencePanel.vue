<template>
  <section class="evaluation-panel card" aria-live="polite">
    <header class="evaluation-head">
      <div class="evaluation-title">
        <span class="evaluation-icon"><ChartNoAxesCombined :size="20" /></span>
        <div>
          <small>MODEL GOVERNANCE</small>
          <h2>离线评测与校准证据</h2>
          <p>这里展示冻结留出集上的模型能力，不参与单次审核，也不等同于线上准确率。</p>
        </div>
      </div>
      <div class="evaluation-actions">
        <span class="evaluation-badge" :class="`state-${status.status}`">{{ statusLabel }}</span>
        <button class="refresh-button" title="刷新评测证据" :disabled="loading" @click="loadEvaluation">
          <RefreshCw :size="16" :class="{ spinning: loading }" />
        </button>
      </div>
    </header>

    <div v-if="loading && !status.tasks.length" class="evaluation-empty"><LoaderCircle :size="18" class="spinning" />正在读取评测证据</div>
    <div v-else-if="error" class="evaluation-empty error"><TriangleAlert :size="18" />{{ error }}</div>
    <template v-else>
      <div class="claim-strip"><ShieldCheck :size="17" /><span>{{ status.claim_level }}</span></div>

      <div class="evidence-summary">
        <span class="success"><b>{{ summary.showcase_strong || 0 }}</b><small>优势能力</small></span>
        <span class="warning"><b>{{ summary.showcase_assist || 0 }}</b><small>辅助能力</small></span>
        <span><b>{{ summary.evaluated || 0 }}</b><small>已完成统计</small></span>
        <span><b>{{ summary.archived || 0 }}</b><small>历史实验归档</small></span>
        <span><b>{{ summary.pending || 0 }}</b><small>证据待补</small></span>
      </div>

      <div class="section-head">
        <div><h3>当前系统实测能力</h3><p>绿色为核心优势能力；橙色为 60%–80% 的辅助审核能力，适合级联复核与人工处置。</p></div>
        <details class="metric-guide">
          <summary><CircleHelp :size="14" />指标说明</summary>
          <div>
            <p><b>Recall</b>：真实风险中被检出的比例，过低会造成漏报。</p>
            <p><b>Precision</b>：模型告警中确为风险的比例，过低会增加人工复核。</p>
            <p><b>F1</b>：Precision 与 Recall 的调和平均，不受多数类准确率迷惑。</p>
            <p><b>ROC / PR-AUC</b>：跨阈值区分能力；正例较少时优先看 PR-AUC。</p>
          </div>
        </details>
      </div>

      <div class="task-grid">
        <article v-for="task in evaluatedTasks" :key="task.task" class="task-item" :class="[`quality-${task.quality_state}`, `tier-${task.showcase_tier}`]">
          <div class="task-top">
            <div><span>{{ taskLabel(task.task) }}</span><small>{{ task.model_version || '模型版本未登记' }}</small></div>
            <b>{{ task.showcase_summary || task.quality_summary || taskStatusLabel(task) }}</b>
          </div>

          <div class="sample-composition">
            <span><Database :size="13" />{{ task.sample_count }} 个样本</span>
            <span v-if="task.positive_count != null">正例 {{ task.positive_count }}</span>
            <span v-if="task.negative_count != null">负例 {{ task.negative_count }}</span>
          </div>

          <div class="primary-metrics">
            <div v-for="metric in primaryMetrics(task)" :key="metric.key">
              <small>{{ metric.label }}</small>
              <strong>{{ metric.value }}</strong>
              <em>{{ metric.interval }}</em>
            </div>
          </div>

          <div class="secondary-metrics">
            <span v-if="task.metrics?.accuracy != null">Accuracy <b>{{ percent(task.metrics.accuracy) }}</b></span>
            <span v-if="task.metrics?.pr_auc != null">PR-AUC <b>{{ decimal(task.metrics.pr_auc) }}</b></span>
            <span v-if="task.metrics?.ece != null">ECE <b>{{ decimal(task.metrics.ece) }}</b></span>
            <span v-if="task.threshold != null">阈值 <b>{{ Number(task.threshold).toFixed(2) }}</b></span>
            <span v-if="task.latency_ms?.mean != null">平均耗时 <b>{{ Math.round(task.latency_ms.mean) }} ms</b></span>
          </div>

          <div v-if="task.confusion_matrix" class="confusion-row">
            <span>检出 <b>{{ task.confusion_matrix.tp }}</b></span>
            <span>漏报 <b>{{ task.confusion_matrix.fn }}</b></span>
            <span>误报 <b>{{ task.confusion_matrix.fp }}</b></span>
            <span>正确排除 <b>{{ task.confusion_matrix.tn }}</b></span>
          </div>

          <footer class="task-foot">
            <span :title="`${task.dataset || ''} · ${task.split || ''}`">{{ task.dataset || '数据集未登记' }} · {{ task.split || '划分未登记' }}</span>
            <code v-if="task.evidence_artifact" :title="task.evidence_artifact"><FileCheck2 :size="12" />{{ task.evidence_artifact }}</code>
          </footer>
        </article>
      </div>

      <section v-if="pendingTasks.length" class="pending-section">
        <div class="section-head compact"><div><h3>证据待办</h3><p>以下项目不构成准确率或 SOTA 结论。</p></div></div>
        <div class="pending-list">
          <div v-for="task in pendingTasks" :key="task.task">
            <span>{{ taskLabel(task.task) }}</span>
            <small>{{ pendingReason(task) }}</small>
            <b>{{ taskStatusLabel(task) }}</b>
          </div>
        </div>
      </section>

      <footer class="panel-foot">
        <span><Database :size="14" />最低门槛：总样本 {{ status.minimum_samples?.total || 30 }}，每类至少 {{ status.minimum_samples?.per_class || 5 }}</span>
        <span v-if="status.latest_evidence"><FileCheck2 :size="14" />最新证据：{{ status.latest_evidence }}</span>
      </footer>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ChartNoAxesCombined, CircleHelp, Database, FileCheck2, LoaderCircle, RefreshCw, ShieldCheck, TriangleAlert } from 'lucide-vue-next'

const loading = ref(false)
const error = ref('')
const status = reactive<Record<string, any>>({ status:'not_calibrated', claim_level:'', tasks:[], summary:{} })

const statusLabel = computed(() => ({
  calibrated:'全部任务具备统计证据', partially_calibrated:'部分任务具备统计证据', smoke_only:'仅完成链路验证', not_calibrated:'暂无校准证据',
} as Record<string,string>)[status.status] || '证据不足')
const summary = computed(() => status.summary || {})
const evaluatedTasks = computed(() => (status.tasks || []).filter((task:Record<string,any>) => task.showcase === true))
const pendingTasks = computed(() => (status.tasks || []).filter((task:Record<string,any>) => task.status !== 'ready'))

const labels: Record<string,string> = {
  'content_safety:multiheaded_q16':'图片安全 · MultiHeaded+Q16 主审核（75张同集复评）',
  'content_safety:perspectivevision':'图片安全 · PerspectiveVision 二次复核（75张同集复评）',
  'deepfake:test':'Deepfake · DF40 测试集', 'deepfake:validation':'Deepfake · DF40 验证集',
  'deepfake:platform_test':'Deepfake · 本平台模型独立测试集',
  'deepfake:platform_validation':'Deepfake · 本平台模型验证集',
  'deepfake:faceforensics_blind':'Deepfake · FaceForensics 盲测',
  'content_safety:adult_content':'图片安全 · 成人内容', 'content_safety:marketing_violation':'图片安全 · 营销违规',
  'content_safety:political_sensitive':'图片安全 · 政治敏感', 'content_safety:weapon_display':'图片安全 · 武器展示',
  'content_safety:violence':'图片安全 · 暴力血腥', 'content_safety:unsafebench':'图片安全 · UnsafeBench',
  'content_safety:personal_data':'图片安全 · PII 泄露', 'content_safety:pii_leakage':'图片安全 · PII 泄露',
  'content_safety:ocr_injection':'图片安全 · OCR 注入',
  'guardrail:singguard':'大模型护栏 · SingGuard-NSFA',
}
const taskLabel = (task:string) => labels[task] || task
const taskStatusLabel = (task:Record<string,any>) => ({
  ready:'统计完成', insufficient_samples:'样本不足', unlabeled:'缺少真值', pending_access:'待获取授权', inconclusive:'无法确认', unknown:'仅链路验证',
} as Record<string,string>)[task.status] || task.status
const pendingReason = (task:Record<string,any>) => task.reason || (task.status === 'unlabeled'
  ? `${task.sample_count || 0} 个预测缺少公开真值，不能计算准确率`
  : task.status === 'pending_access' ? `数据规模 ${task.sample_count || '未知'}，尚未完成合规获取与本地推理`
  : `${task.sample_count || 0} 个样本，未达到发布门槛`)
const percent = (value:number) => `${(Number(value) * 100).toFixed(1)}%`
const decimal = (value:number) => Number(value).toFixed(3)
const interval = (values?:number[]) => values?.length === 2
  ? `95% CI ${percent(values[0])}–${percent(values[1])}` : '95% CI 未提供'
function primaryMetrics(task:Record<string,any>) {
  const metrics = task.metrics || {}
  return [
    { key:'recall', label:'召回率 Recall', value:metrics.recall == null ? '—' : percent(metrics.recall), interval:interval(metrics.recall_95ci) },
    { key:'precision', label:'精确率 Precision', value:metrics.precision == null ? '—' : percent(metrics.precision), interval:interval(metrics.precision_95ci) },
    { key:'f1', label:'综合 F1', value:metrics.f1 == null ? '—' : decimal(metrics.f1), interval:interval(metrics.f1_95ci) },
    { key:'roc_auc', label:'ROC-AUC', value:metrics.roc_auc == null ? '—' : decimal(metrics.roc_auc), interval:interval(metrics.roc_auc_95ci) },
  ]
}

async function loadEvaluation() {
  loading.value = true
  error.value = ''
  try {
    const response = await fetch('/api/system/evaluation')
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    Object.assign(status, await response.json())
  } catch {
    error.value = '评测证据暂时无法读取，请检查后台服务。'
  } finally {
    loading.value = false
  }
}
onMounted(loadEvaluation)
</script>

<style scoped>
.evaluation-panel{padding:0;overflow:hidden}.evaluation-head{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;padding:20px 24px;border-bottom:1px solid var(--line)}.evaluation-title{display:flex;gap:13px;min-width:0}.evaluation-icon{width:40px;height:40px;display:grid;place-items:center;flex:0 0 40px;color:var(--primary);background:rgba(8,126,174,.08);border:1px solid rgba(8,126,174,.18);border-radius:7px}.evaluation-title small{color:var(--primary);font-size:10px;font-weight:750}.evaluation-title h2{margin:3px 0 5px;font-size:17px}.evaluation-title p{margin:0;color:var(--muted);font-size:12px;line-height:1.55}.evaluation-actions{display:flex;align-items:center;gap:9px}.evaluation-badge{min-height:32px;display:inline-flex;align-items:center;padding:0 11px;border:1px solid var(--line);border-radius:5px;color:var(--muted);background:var(--surface-2);font-size:11px;font-weight:700;white-space:nowrap}.evaluation-badge.state-partially_calibrated,.evaluation-badge.state-smoke_only{color:var(--warning);background:rgba(184,111,18,.07);border-color:rgba(184,111,18,.22)}.evaluation-badge.state-calibrated{color:var(--success);background:rgba(22,128,94,.07);border-color:rgba(22,128,94,.2)}.refresh-button{width:34px;height:34px;display:grid;place-items:center;color:var(--muted);background:#fff;border:1px solid var(--line);border-radius:6px;cursor:pointer}.claim-strip{display:flex;align-items:center;gap:9px;margin:16px 24px 0;padding:11px 13px;color:var(--muted);background:var(--surface-2);border-left:3px solid var(--primary);font-size:11px}.claim-strip svg{color:var(--primary);flex:0 0 auto}.evidence-summary{display:grid;grid-template-columns:repeat(5,1fr);gap:1px;margin:14px 24px 4px;background:var(--line);border:1px solid var(--line);border-radius:7px;overflow:hidden}.evidence-summary span{display:flex;align-items:baseline;gap:8px;padding:12px;background:#fff}.evidence-summary b{font-size:20px}.evidence-summary small{color:var(--muted);font-size:10px}.evidence-summary .success b{color:var(--success)}.evidence-summary .warning b{color:var(--warning)}.evidence-summary .danger b{color:var(--danger)}.section-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;padding:18px 24px 8px}.section-head h3{margin:0 0 3px;font-size:13px}.section-head p{margin:0;color:var(--muted);font-size:10px}.metric-guide{position:relative;color:var(--muted);font-size:10px}.metric-guide summary{display:flex;align-items:center;gap:5px;cursor:pointer;list-style:none}.metric-guide>div{position:absolute;z-index:4;right:0;width:310px;margin-top:7px;padding:11px 13px;background:#fff;border:1px solid var(--line);border-radius:6px;box-shadow:0 8px 24px rgba(18,45,63,.13)}.metric-guide p{margin:5px 0;line-height:1.55}.task-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;padding:4px 24px 18px}.task-item{min-width:0;padding:14px;background:#fff;border:1px solid var(--line);border-top:3px solid var(--success);border-radius:7px}.task-item.quality-unsafe_for_automation{border-top-color:var(--danger)}.task-item.quality-limited,.task-item.quality-limited_evidence{border-top-color:var(--warning)}.task-top{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.task-top>div{min-width:0}.task-top span{display:block;color:var(--text);font-size:13px;font-weight:700}.task-top small{display:block;margin-top:3px;overflow:hidden;color:var(--faint);font-size:9px;text-overflow:ellipsis;white-space:nowrap}.task-top b{max-width:45%;padding:4px 7px;color:var(--success);background:rgba(22,128,94,.07);border-radius:4px;font-size:9px;text-align:right}.quality-unsafe_for_automation .task-top b{color:var(--danger);background:rgba(193,50,60,.07)}.quality-limited .task-top b,.quality-limited_evidence .task-top b{color:var(--warning);background:rgba(184,111,18,.07)}.sample-composition{display:flex;gap:8px;margin-top:11px}.sample-composition span{display:flex;align-items:center;gap:4px;padding:3px 6px;color:var(--muted);background:var(--surface-2);border-radius:4px;font-size:9px}.primary-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-top:10px}.primary-metrics>div{min-width:0;padding:9px;background:var(--surface-2);border-radius:5px}.primary-metrics small,.primary-metrics em{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.primary-metrics small{color:var(--muted);font-size:8px}.primary-metrics strong{display:block;margin:4px 0 2px;font:700 17px ui-monospace,monospace}.primary-metrics em{color:var(--faint);font-size:7px;font-style:normal}.secondary-metrics{display:flex;flex-wrap:wrap;gap:11px;margin-top:9px;color:var(--muted);font-size:9px}.secondary-metrics b{color:var(--text)}.confusion-row{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;margin-top:10px;background:var(--line);border:1px solid var(--line);border-radius:5px;overflow:hidden}.confusion-row span{padding:6px;background:#fff;color:var(--muted);font-size:8px;text-align:center}.confusion-row b{color:var(--text);font-size:10px}.quality-unsafe_for_automation .confusion-row span:nth-child(2) b{color:var(--danger)}.task-foot{display:flex;justify-content:space-between;gap:10px;margin-top:10px;padding-top:9px;border-top:1px solid var(--line)}.task-foot span,.task-foot code{min-width:0;overflow:hidden;color:var(--faint);font-size:8px;text-overflow:ellipsis;white-space:nowrap}.task-foot span{max-width:55%}.task-foot code{display:flex;align-items:center;gap:4px}.pending-section{padding-bottom:15px;border-top:1px solid var(--line)}.section-head.compact{padding-top:15px}.pending-list{margin:2px 24px 0;border:1px solid var(--line);border-radius:6px;overflow:hidden}.pending-list>div{display:grid;grid-template-columns:minmax(180px,.8fr) minmax(260px,1.5fr) auto;align-items:center;gap:14px;padding:9px 11px;border-bottom:1px solid var(--line)}.pending-list>div:last-child{border:0}.pending-list span{font-size:10px;font-weight:650}.pending-list small{color:var(--muted);font-size:9px}.pending-list b{color:var(--warning);font-size:9px}.panel-foot{display:flex;justify-content:space-between;gap:12px;padding:12px 24px;background:var(--surface-2);border-top:1px solid var(--line);color:var(--faint);font-size:9px}.panel-foot span{display:flex;align-items:center;gap:6px;min-width:0}.evaluation-empty{min-height:130px;display:flex;align-items:center;justify-content:center;gap:8px;color:var(--muted);font-size:11px}.evaluation-empty.error{color:var(--danger)}.spinning{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
@media(max-width:1000px){.evidence-summary{grid-template-columns:repeat(3,1fr)}.task-grid{grid-template-columns:1fr}}@media(max-width:680px){.evaluation-head{flex-direction:column}.evaluation-actions{width:100%;justify-content:space-between}.evidence-summary{grid-template-columns:repeat(2,1fr)}.evidence-summary span:last-child:nth-child(odd){grid-column:1/-1}.primary-metrics{grid-template-columns:repeat(2,1fr)}.pending-list>div{grid-template-columns:1fr;gap:4px}.panel-foot{align-items:flex-start;flex-direction:column}.metric-guide>div{right:-12px;width:min(310px,80vw)}}
.task-item.tier-assist{border-top-color:var(--warning)}
.task-item.tier-assist .task-top b{color:var(--warning);background:rgba(184,111,18,.07)}
</style>
