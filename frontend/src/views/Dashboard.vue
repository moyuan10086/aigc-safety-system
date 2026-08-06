<template>
  <div class="dashboard-page">
    <header class="page-heading">
      <div><p>AIGC SECURITY OPERATIONS</p><h1>AIGC 安全运营台</h1><span class="platform-scope">真实性鉴别 + 敏感内容与安全风险审核</span></div>
      <div class="mode-switch" aria-label="运营台模式">
        <button @click="router.push('/detect')"><ScanLine :size="15" />标准工作台</button>
        <button class="active"><LayoutDashboard :size="15" />数据总览</button>
        <button @click="enterBigScreen"><MonitorUp :size="15" />大屏模式</button>
      </div>
    </header>

    <div class="dashboard-toolbar">
      <div class="range-switch" aria-label="统计时间窗口">
        <button v-for="item in ranges" :key="item.value" :class="{ active: hours === item.value }" @click="hours = item.value">{{ item.label }}</button>
      </div>
      <span v-if="data" class="generated-at">更新于 {{ formatDate(data.generated_at) }}</span>
      <button class="icon-command" title="刷新数据" :disabled="loading" @click="refresh(true)"><RefreshCw :size="16" :class="{ spinning: loading }" /></button>
    </div>

    <div v-if="authRequired" class="access-state">
      <LockKeyhole :size="26" /><strong>驾驶舱仅对审核员开放</strong><button @click="openLogin">登录审核员账号</button>
    </div>
    <div v-else-if="error && !data" class="access-state error"><CircleAlert :size="26" /><strong>{{ error }}</strong><button @click="refresh(true)">重新加载</button></div>
    <template v-else-if="data">
      <div class="metric-grid">
        <MetricCard :icon="ClipboardCheck" label="审核量" :value="data.summary.business_reviews" :detail="`${data.window.hours} 小时内真实审核任务`" tone="primary" />
        <MetricCard :icon="ShieldAlert" label="风险告警" :value="data.summary.alerts" :detail="`阻断 ${data.summary.blocked} 次 · ${data.summary.block_rate}%`" tone="danger" />
        <MetricCard :icon="Activity" label="接口调用" :value="data.summary.request_count" :detail="`成功率 ${data.summary.success_rate}%`" tone="success" />
        <MetricCard :icon="Timer" label="P95 延迟" :value="`${data.summary.p95_latency_ms} ms`" :detail="`平均 ${data.summary.average_latency_ms} ms`" tone="warning" />
        <MetricCard :icon="Network" label="来源 IP" :value="data.summary.unique_clients" :detail="`${data.summary.unique_actors} 个操作者`" />
        <MetricCard :icon="FileCheck2" label="检测报告" :value="data.reports.in_window" :detail="`累计 ${data.reports.total} 份`" />
      </div>

      <div class="dashboard-grid main-grid">
        <DashboardPanel title="审核与风险趋势" :subtitle="`${data.window.bucket_hours} 小时粒度`" class="trend-panel"><BaseChart :option="trendOption" aria-label="审核与风险趋势图" /></DashboardPanel>
        <DashboardPanel title="风险分布" subtitle="按护栏类别统计"><div v-if="data.risk_distribution.length" class="chart-box"><BaseChart :option="riskOption" aria-label="风险类别分布图" /></div><div v-else class="empty-state">当前窗口暂无风险分类</div></DashboardPanel>
      </div>

      <div class="dashboard-grid detail-grid">
        <DashboardPanel title="模型与引擎状态" subtitle="配置态与运行链路分开显示">
          <div class="model-list"><div v-for="model in data.models" :key="model.id" class="model-row"><i :class="model.status"></i><div><strong>{{ model.label }}</strong><span>{{ model.model }}</span></div><b>{{ statusLabel(model.status) }}</b></div></div>
        </DashboardPanel>
        <DashboardPanel title="来源与调用量" subtitle="仅展示结构化来源信息">
          <div v-if="data.top_sources.length" class="source-list"><div v-for="source in data.top_sources" :key="source.client_ip" class="source-row"><code>{{ source.client_ip }}</code><span>{{ source.events }} 次</span><b v-if="source.alerts">{{ source.alerts }} 告警</b></div></div><div v-else class="empty-state">当前窗口暂无来源数据</div>
        </DashboardPanel>
        <DashboardPanel title="实时告警" subtitle="不包含原始提示词和危险输出">
          <div v-if="data.recent_alerts.length" class="alert-list"><div v-for="alert in data.recent_alerts.slice(0, 6)" :key="alert.id" class="alert-row"><i :class="alert.severity"></i><div><strong>{{ alert.risk_code || alert.module }}</strong><span>{{ alert.summary }}</span></div><time>{{ formatTime(alert.occurred_at) }}</time></div></div><div v-else class="empty-state">当前窗口暂无风险告警</div>
        </DashboardPanel>
      </div>

      <DashboardPanel title="人工复核样本池" subtitle="主判保持生效；真实人工标签用于评测、校准与比赛证据" class="shadow-review-panel">
        <ShadowReviewPanel :summary="data.shadow_evaluation" :items="data.shadow_reviews" :busy-event-id="reviewingEventId" @inspect="inspectAuditEvent" />
      </DashboardPanel>

      <footer class="data-foot"><Database :size="14" /><span>{{ data.data_sources.join(' · ') }}</span><b :class="{ healthy: data.service_health.audit_chain === 'healthy' }">审计链{{ data.service_health.audit_chain === 'healthy' ? '完整' : '异常' }}</b><b>原始证据加密保留</b></footer>
    </template>
    <AuditLogDetail
      :event="selectedAuditEvent"
      :review-item="selectedReviewItem"
      :busy="Boolean(selectedAuditEvent && reviewingEventId === selectedAuditEvent.id)"
      @close="selectedAuditEvent = null"
      @evidence-revealed="handleEvidenceRevealed"
      @resolve="handleShadowReview"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { EChartsCoreOption } from 'echarts/core'
import { Activity, CircleAlert, ClipboardCheck, Database, FileCheck2, LayoutDashboard, LockKeyhole, MonitorUp, Network, RefreshCw, ScanLine, ShieldAlert, Timer } from 'lucide-vue-next'
import { toast } from 'vue3-toastify'
import AuditLogDetail from '../components/audit/AuditLogDetail.vue'
import type { AuditEvent } from '../composables/useAuditLogs'
import BaseChart from '../components/dashboard/BaseChart.vue'
import DashboardPanel from '../components/dashboard/DashboardPanel.vue'
import MetricCard from '../components/dashboard/MetricCard.vue'
import ShadowReviewPanel from '../components/dashboard/ShadowReviewPanel.vue'
import { useDashboard } from '../composables/useDashboard'

const router = useRouter()
const { data, hours, loading, error, authRequired, reviewingEventId, refresh, claimReview, resolveShadowReview, openLogin } = useDashboard()
const selectedAuditEvent = ref<AuditEvent | null>(null)
const selectedReviewItem = computed(() => data.value?.shadow_reviews.find(item => item.event_id === selectedAuditEvent.value?.id) || null)
const ranges = [{ label: '24 小时', value: 24 }, { label: '3 天', value: 72 }, { label: '7 天', value: 168 }]
const categoryNames: Record<string, string> = { jailbreak: '越狱攻击', prompt_injection: '提示词注入', cyber_abuse: '网络攻击滥用', weapons_violence: '武器暴力', self_harm: '自伤风险', sexual_content: '色情内容', child_safety: '未成年人安全', personal_data: '隐私数据', illegal_activity: '违法活动', agent_security: 'Agent 安全', adult_content: '成人内容', weapon_display: '武器展示', graphic_violence: '暴力血腥', political_sensitive: '政治敏感', marketing_violation: '营销违规' }
const chartText = '#5d7082'
const gridLine = '#e8edf2'

const trendOption = computed<EChartsCoreOption>(() => ({
  animationDuration: 500,
  tooltip: { trigger: 'axis' },
  legend: { top: 2, right: 4, textStyle: { color: chartText, fontSize: 10 }, data: ['安全事件', '风险告警', '阻断'] },
  grid: { left: 42, right: 18, top: 38, bottom: 30 },
  xAxis: { type: 'category', boundaryGap: false, data: data.value?.timeline.map(item => formatAxis(item.start)) || [], axisLine: { lineStyle: { color: gridLine } }, axisLabel: { color: chartText, fontSize: 9 } },
  yAxis: { type: 'value', minInterval: 1, axisLabel: { color: chartText, fontSize: 9 }, splitLine: { lineStyle: { color: gridLine } } },
  series: [
    { name: '安全事件', type: 'line', smooth: true, showSymbol: false, areaStyle: { color: 'rgba(8,126,174,.10)' }, lineStyle: { color: '#087eae', width: 2 }, data: data.value?.timeline.map(item => item.events) || [] },
    { name: '风险告警', type: 'line', smooth: true, showSymbol: false, lineStyle: { color: '#b86f12', width: 2 }, data: data.value?.timeline.map(item => item.alerts) || [] },
    { name: '阻断', type: 'line', smooth: true, showSymbol: false, lineStyle: { color: '#cf3f4f', width: 2 }, data: data.value?.timeline.map(item => item.blocked) || [] },
  ],
}))

const riskOption = computed<EChartsCoreOption>(() => ({
  tooltip: { trigger: 'item' },
  legend: { bottom: 0, left: 'center', textStyle: { color: chartText, fontSize: 9 } },
  color: ['#cf3f4f', '#b86f12', '#087eae', '#16805e', '#7356a8', '#5d7082'],
  series: [{ type: 'pie', radius: ['48%', '70%'], center: ['50%', '43%'], label: { show: false }, data: data.value?.risk_distribution.map(item => ({ name: categoryNames[item.name] || item.name, value: item.value })) || [] }],
}))

async function enterBigScreen() {
  try { await document.documentElement.requestFullscreen() } catch { /* Browser may deny fullscreen; route still provides a viewport-filling mode. */ }
  router.push('/dashboard/screen')
}
async function handleShadowReview(eventId: string, reviewLabel: 'safe' | 'borderline' | 'unsafe', reviewNote = '') {
  try {
    const result = await resolveShadowReview(eventId, reviewLabel, reviewNote)
    toast.success('人工复核标签已写入审计闭环')
    if (result?.next_event_id) {
      await inspectAuditEvent(result.next_event_id, false)
      toast.info('已自动领取并打开下一条复核样本')
    }
  } catch (caught) {
    toast.error((caught as Error).message)
  }
}
async function inspectAuditEvent(eventId: string, shouldClaim = true) {
  try {
    if (shouldClaim) {
      await claimReview(eventId)
      await refresh(true)
    }
    const response = await fetch(`/api/audit/logs/${eventId}`, { credentials: 'same-origin' })
    const body = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : '审计事件读取失败')
    selectedAuditEvent.value = body
  } catch (caught) {
    toast.error((caught as Error).message)
  }
}
async function handleEvidenceRevealed() {
  await refresh(true)
  toast.info('证据访问已审计，现在可以提交人工标签')
}
function formatDate(value: string) { return new Date(value).toLocaleString('zh-CN', { hour12: false }) }
function formatTime(value: string) { return new Date(value).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false }) }
function formatAxis(value: string) { const date = new Date(value); return hours.value <= 48 ? `${date.getHours().toString().padStart(2, '0')}:00` : `${date.getMonth() + 1}/${date.getDate()} ${date.getHours().toString().padStart(2, '0')}:00` }
function statusLabel(status: string) { return ({ enabled: '已启用', configured: '已配置', standby: '待机', degraded: '需检查', unconfigured: '未配置' } as Record<string, string>)[status] || status }
</script>

<style scoped>
.dashboard-page{width:100%;max-width:1540px;margin:0 auto}.page-heading{display:flex;align-items:flex-end;gap:18px;margin-bottom:16px}.page-heading p{margin:0 0 5px;color:var(--primary);font:700 9px/1 ui-monospace,monospace}.page-heading h1{margin:0;font-size:20px}.mode-switch,.range-switch{display:flex;padding:3px;background:var(--surface);border:1px solid var(--line);border-radius:7px;box-shadow:var(--shadow-sm)}.mode-switch{margin-left:auto}.mode-switch button,.range-switch button{height:32px;display:flex;align-items:center;justify-content:center;gap:7px;padding:0 12px;color:var(--muted);background:transparent;border:0;border-radius:5px;font-size:11px;cursor:pointer}.mode-switch button.active,.range-switch button.active{color:#fff;background:var(--primary);font-weight:650}.dashboard-toolbar{height:42px;display:flex;align-items:center;gap:10px;margin-bottom:14px}.generated-at{margin-left:auto;color:var(--faint);font-size:10px}.dashboard-toolbar .icon-command:disabled{cursor:wait;opacity:.6}.spinning{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}.metric-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px;margin-bottom:12px}.dashboard-grid{display:grid;gap:12px;margin-bottom:12px}.main-grid{grid-template-columns:minmax(0,2fr) minmax(300px,.8fr)}.detail-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.main-grid .dashboard-panel{height:340px}.detail-grid .dashboard-panel{height:320px}.shadow-review-panel{margin-bottom:12px}.shadow-review-panel :deep(.panel-body){padding:0}.chart-box{height:260px}.trend-panel :deep(.panel-body){height:284px;padding:6px 10px 10px}.model-list,.source-list,.alert-list{display:flex;flex-direction:column}.model-row,.source-row,.alert-row{min-height:50px;display:flex;align-items:center;gap:10px;border-bottom:1px solid var(--line)}.model-row:last-child,.source-row:last-child,.alert-row:last-child{border-bottom:0}.model-row i,.alert-row i{width:8px;height:8px;flex:0 0 8px;border-radius:50%;background:var(--faint)}.model-row i.enabled,.model-row i.configured{background:var(--success);box-shadow:0 0 8px rgba(22,128,94,.35)}.model-row i.standby{background:var(--warning)}.model-row>div,.alert-row>div{min-width:0;display:flex;flex:1;flex-direction:column}.model-row strong,.alert-row strong{color:var(--text);font-size:11px}.model-row span,.alert-row span{margin-top:3px;color:var(--faint);font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.model-row b{color:var(--muted);font-size:9px}.source-row code{color:var(--text);font-size:10px}.source-row span{margin-left:auto;color:var(--muted);font-size:10px}.source-row b{color:var(--danger);font-size:9px}.alert-row i.warning{background:var(--warning)}.alert-row i.high,.alert-row i.critical{background:var(--danger)}.alert-row time{color:var(--faint);font-size:9px}.empty-state{height:230px;display:grid;place-items:center;color:var(--faint);font-size:11px}.access-state{min-height:330px;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:12px;color:var(--muted);background:var(--surface);border:1px solid var(--line);border-radius:8px}.access-state button{height:34px;padding:0 14px;color:#fff;background:var(--primary);border:0;border-radius:6px;cursor:pointer}.access-state.error{color:var(--danger)}.data-foot{min-height:42px;display:flex;align-items:center;gap:8px;padding:0 12px;color:var(--faint);background:var(--surface);border:1px solid var(--line);border-radius:7px;font-size:9px}.data-foot span{flex:1}.data-foot b{padding:3px 6px;color:var(--muted);background:var(--surface-3);border-radius:4px}.data-foot b.healthy{color:var(--success)}@media(max-width:1260px){.metric-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.detail-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:860px){.page-heading{align-items:flex-start;flex-direction:column}.mode-switch{width:100%;margin-left:0}.mode-switch button{flex:1}.main-grid,.detail-grid{grid-template-columns:minmax(0,1fr)}.detail-grid .dashboard-panel{height:auto;min-height:280px}}@media(max-width:600px){.metric-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.metric-card{height:112px}.dashboard-toolbar{flex-wrap:wrap;height:auto}.generated-at{order:3;width:100%;margin-left:0}.data-foot{align-items:flex-start;flex-wrap:wrap;padding:10px}.data-foot span{flex-basis:100%}}
.model-row i.degraded{background:var(--danger)}
.platform-scope{display:block;margin-top:5px;color:var(--muted);font-size:10px}
</style>
