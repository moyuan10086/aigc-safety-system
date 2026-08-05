<template>
  <div class="big-screen">
    <header class="screen-header">
      <div class="brand-lockup"><ShieldCheck :size="24" /><div><strong>AIGC 安全运营台</strong><span>MULTIMODAL CONTENT SAFETY</span></div></div>
      <div class="screen-title">AIGC 安全可视化驾驶舱</div>
      <div class="screen-clock"><strong>{{ clock }}</strong><span>{{ date }}</span><button title="退出大屏" @click="exitScreen"><Minimize2 :size="17" /></button></div>
    </header>

    <div v-if="authRequired" class="screen-state"><LockKeyhole :size="28" /><strong>审核员会话已失效</strong><button @click="openLogin">重新登录</button></div>
    <div v-else-if="!data" class="screen-state"><LoaderCircle :size="28" class="spin" /><strong>{{ error || '正在汇聚安全数据' }}</strong></div>
    <template v-else>
      <div class="screen-kpis">
        <div><span>审核任务</span><strong>{{ data.summary.business_reviews }}</strong><small>{{ data.window.hours }}H WINDOW</small></div>
        <div><span>安全事件</span><strong>{{ data.summary.total_events }}</strong><small>REAL AUDIT</small></div>
        <div class="risk"><span>风险告警</span><strong>{{ data.summary.alerts }}</strong><small>阻断 {{ data.summary.blocked }}</small></div>
        <div><span>来源主体</span><strong>{{ data.summary.unique_clients }}</strong><small>PUBLIC + INTERNAL</small></div>
        <div><span>P95 延迟</span><strong>{{ data.summary.p95_latency_ms }}</strong><small>MS · 健康 {{ latencyHealthScore(data.summary.p95_latency_ms) }}</small></div>
        <div><span>检测报告</span><strong>{{ data.reports.in_window }}</strong><small>{{ data.reports.total }} TOTAL</small></div>
      </div>

      <main class="screen-grid">
        <div class="screen-column left-column">
          <CockpitPanel class="intro-panel" title="平台简介" code="PLATFORM PROFILE">
            <div class="platform-intro">
              <p>平台不以“反 AI”为目标，而是把真实性、内容安全、来源凭证与人工复核编排为同一条审计链，识别伪造、风险与缺乏可追溯依据的自动化内容。</p>
              <p class="intro-future">红线知识库覆盖敏感内容、隐私、违法诱导和提示注入；可扩展搜索支撑的事实核验，将待验证主张送入审计队列。</p>
              <div class="capability-tags"><span>真实性审计</span><span>内容安全</span><span>大模型护栏</span><span>C2PA 溯源</span></div>
              <dl><div><dt>公网来源</dt><dd>{{ sourceBreakdown.public }}</dd></div><div><dt>内部 / 测试</dt><dd>{{ sourceBreakdown.internal }}</dd></div><div><dt>原图公开</dt><dd>否</dd></div></dl>
            </div>
          </CockpitPanel>
          <CockpitPanel class="trend" title="审核与告警趋势" code="EVENT TREND"><BaseChart :option="trendOption" aria-label="大屏审核与告警趋势图" dark /></CockpitPanel>
          <CockpitPanel class="ring" title="风险类别分布" code="RISK PROFILE"><BaseChart :option="riskOption" aria-label="大屏风险类别环形图" dark /></CockpitPanel>
        </div>

        <CockpitPanel class="situation" title="多模态审核防御链" code="DEFENSE PIPELINE">
          <SecurityPipeline :configured="data.service_health.configured_models" :total="data.service_health.total_models" />
          <div class="situation-foot"><span><i></i>主系统在线</span><span><i class="cyan"></i>{{ data.service_health.configured_models }}/{{ data.service_health.total_models }} 引擎就绪</span><span><i :class="{ danger: data.service_health.audit_chain !== 'healthy' }"></i>审计链{{ data.service_health.audit_chain === 'healthy' ? '完整' : '异常' }}</span></div>
        </CockpitPanel>

        <div class="screen-column right-column">
          <CockpitPanel class="alerts" title="实时风险事件" code="LIVE ALERTS">
            <div v-if="data.recent_alerts.length" class="ticker"><div v-for="alert in data.recent_alerts.slice(0, 7)" :key="alert.id"><time>{{ formatTime(alert.occurred_at) }}</time><b :class="alert.severity">{{ alert.risk_code || alert.module }}</b><span>{{ alert.summary }}</span><code>{{ sourceLabel(alert.client_ip) }}</code></div></div>
            <div v-else class="screen-empty">当前窗口暂无风险告警</div>
          </CockpitPanel>
          <CockpitPanel class="radar" title="防护能力态势" code="CONTROL POSTURE"><BaseChart :option="radarOption" aria-label="防护能力雷达图" dark /></CockpitPanel>
          <CockpitPanel class="engines" title="模型与引擎" code="ENGINE STATUS"><div class="engine-grid"><div v-for="model in data.models.slice(0, 8)" :key="model.id"><i :class="model.status"></i><span>{{ model.label }}</span><strong>{{ statusLabel(model.status) }}</strong><small>{{ model.model }}</small></div></div></CockpitPanel>
        </div>

        <CockpitPanel class="samples-panel" title="典型风险样本实测" code="CURATED BENCHMARK · SANITIZED"><RiskSampleStrip :samples="demoSamples" /></CockpitPanel>
      </main>
      <footer class="screen-footer"><span>数据窗口 {{ data.window.start }} → {{ data.window.end }}</span><span>样本：合成演示 / 公开夹具 / 授权仓库 · 敏感图已脱敏</span><strong>原始提示词与危险输出：AES-GCM 加密留存</strong><i :class="{ spin: loading }"></i></footer>
    </template>
    <LoginDialog :open="loginOpen" @close="loginOpen = false" />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { EChartsCoreOption } from 'echarts/core'
import { LoaderCircle, LockKeyhole, Minimize2, ShieldCheck } from 'lucide-vue-next'
import BaseChart from '../components/dashboard/BaseChart.vue'
import LoginDialog from '../components/auth/LoginDialog.vue'
import CockpitPanel from '../components/dashboard/CockpitPanel.vue'
import RiskSampleStrip, { type DemoRiskSample } from '../components/dashboard/RiskSampleStrip.vue'
import SecurityPipeline from '../components/dashboard/SecurityPipeline.vue'
import { useDashboard } from '../composables/useDashboard'

const router = useRouter()
const { data, loading, error, authRequired } = useDashboard()
const now = ref(new Date())
const demoSamples = ref<DemoRiskSample[]>([])
const loginOpen = ref(false)
let clockTimer: ReturnType<typeof setInterval> | null = null
let sampleController: AbortController | null = null
const clock = computed(() => now.value.toLocaleTimeString('zh-CN', { hour12: false }))
const date = computed(() => now.value.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', weekday: 'short' }))
const riskColors = ['#ff5869', '#ffb454', '#31c6dc', '#4ddeaa', '#9b8cff', '#8fa8b8']
const categoryNames: Record<string, string> = { jailbreak: '越狱攻击', prompt_injection: '提示词注入', cyber_abuse: '网络攻击滥用', weapons_violence: '武器暴力', self_harm: '自伤风险', sexual_content: '色情内容', child_safety: '未成年人安全', personal_data: '隐私数据', illegal_activity: '违法活动', agent_security: 'Agent 安全', adult_content: '成人内容', weapon_display: '武器展示', graphic_violence: '暴力血腥', political_sensitive: '政治敏感', marketing_violation: '营销违规' }

function sourceScope(value?: string): 'public' | 'internal' {
  const source = (value || '').trim().toLowerCase()
  if (source === 'internal' || source === 'testclient' || source === 'localhost') return 'internal'
  const parts = source.split('.').map(Number)
  if (parts.length !== 4 || parts.some(part => !Number.isInteger(part) || part < 0 || part > 255)) return 'internal'
  if (parts[0] === 10 || parts[0] === 127 || (parts[0] === 192 && parts[1] === 168) || (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31)) return 'internal'
  return 'public'
}

const sourceBreakdown = computed(() => (data.value?.top_sources || []).reduce((totals, source) => {
  totals[sourceScope(source.client_ip)] += 1
  return totals
}, { public: 0, internal: 0 } as Record<'public' | 'internal', number>))

const trendOption = computed<EChartsCoreOption>(() => ({
  backgroundColor: 'transparent', tooltip: { trigger: 'axis' },
  grid: { left: 34, right: 10, top: 22, bottom: 22 },
  xAxis: { type: 'category', boundaryGap: false, data: data.value?.timeline.map(item => new Date(item.start).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })) || [], axisLine: { lineStyle: { color: '#244d68' } }, axisLabel: { color: '#6f94aa', fontSize: 7 } },
  yAxis: { type: 'value', minInterval: 1, axisLabel: { color: '#6f94aa', fontSize: 7 }, splitLine: { lineStyle: { color: 'rgba(64,132,169,.15)' } } },
  series: [
    { name: '审核', type: 'line', smooth: true, showSymbol: false, lineStyle: { color: '#31c6dc', width: 2 }, areaStyle: { color: 'rgba(49,198,220,.10)' }, data: data.value?.timeline.map(item => item.events) || [] },
    { name: '告警', type: 'line', smooth: true, showSymbol: false, lineStyle: { color: '#ff5869', width: 1.5 }, data: data.value?.timeline.map(item => item.alerts) || [] },
  ],
}))
const riskOption = computed<EChartsCoreOption>(() => ({
  backgroundColor: 'transparent', tooltip: { trigger: 'item' }, color: riskColors,
  legend: { type: 'scroll', orient: 'vertical', right: 8, top: 'middle', height: '82%', width: '48%', itemGap: 5, selectedMode: false, pageIconSize: 6, pageTextStyle: { color: '#6f94aa', fontSize: 6 }, textStyle: { color: '#7fa2b6', fontSize: 7, overflow: 'truncate', width: 90 }, itemWidth: 7, itemHeight: 7, formatter: (name: string) => categoryNames[name] || name },
  series: [{ type: 'pie', radius: ['39%', '62%'], center: ['25%', '52%'], label: { show: false }, data: data.value?.risk_distribution.length ? data.value.risk_distribution : [{ name: '无风险事件', value: 1, itemStyle: { color: '#244d68' } }] }],
}))

function latencyHealthScore(p95LatencyMs: number) {
  const healthyMs = 5_000
  const criticalMs = 60_000
  if (p95LatencyMs <= healthyMs) return 100
  if (p95LatencyMs >= criticalMs) return 0
  return Math.round(100 * (criticalMs - p95LatencyMs) / (criticalMs - healthyMs))
}

const radarOption = computed<EChartsCoreOption>(() => {
  const summary = data.value?.summary
  const models = data.value?.service_health
  const incidentHandled = summary?.alerts ? Math.min(100, Math.round((summary.blocked / summary.alerts) * 100)) : 100
  const latencyHealth = summary ? latencyHealthScore(summary.p95_latency_ms) : 0
  return {
    backgroundColor: 'transparent', tooltip: {},
    radar: { radius: '58%', center: ['50%', '53%'], indicator: [{ name: '成功率', max: 100 }, { name: '响应健康', max: 100 }, { name: '风险处置', max: 100 }, { name: '审计完整', max: 100 }, { name: '引擎就绪', max: 100 }], axisName: { color: '#7fa2b6', fontSize: 8 }, splitArea: { areaStyle: { color: ['rgba(49,198,220,.02)', 'rgba(49,198,220,.06)'] } }, splitLine: { lineStyle: { color: '#24506b' } }, axisLine: { lineStyle: { color: '#24506b' } } },
    series: [{ type: 'radar', data: [{ value: [summary?.success_rate || 0, latencyHealth, incidentHandled, data.value?.service_health.audit_chain === 'healthy' ? 100 : 0, models ? Math.round(models.configured_models / models.total_models * 100) : 0], areaStyle: { color: 'rgba(49,198,220,.20)' }, lineStyle: { color: '#31c6dc', width: 2 }, itemStyle: { color: '#4ddeaa' } }] }],
  }
})

async function loadDemoSamples() {
  sampleController?.abort()
  sampleController = new AbortController()
  try {
    const response = await fetch('/demo-samples/catalog.json', { signal: sampleController.signal, cache: 'no-store' })
    if (!response.ok) return
    const body = await response.json()
    demoSamples.value = Array.isArray(body.samples) ? body.samples : []
  } catch (caught) {
    if ((caught as Error).name !== 'AbortError') demoSamples.value = []
  }
}

function openLogin() { loginOpen.value = true }
async function exitScreen() { if (document.fullscreenElement) await document.exitFullscreen().catch(() => undefined); router.push('/dashboard') }
function formatTime(value: string) { return new Date(value).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) }
function sourceLabel(value?: string) { return sourceScope(value) === 'public' ? (value || '公网') : '内部 / 测试' }
function statusLabel(status: string) { return ({ enabled: '运行', configured: '就绪', standby: '待机', degraded: '异常', unconfigured: '未配置' } as Record<string, string>)[status] || status }
onMounted(() => { clockTimer = setInterval(() => { now.value = new Date() }, 1000); loadDemoSamples() })
onBeforeUnmount(() => { if (clockTimer) clearInterval(clockTimer); sampleController?.abort() })
</script>

<style scoped>
:global(body:has(.big-screen)){overflow:hidden}.big-screen{position:fixed;inset:0;z-index:500;display:flex;flex-direction:column;min-width:1024px;min-height:640px;box-sizing:border-box;padding:10px 14px 8px;color:#d9edf7;background:#071b2a;background-image:linear-gradient(rgba(62,135,171,.075) 1px,transparent 1px),linear-gradient(90deg,rgba(62,135,171,.075) 1px,transparent 1px);background-size:38px 38px}.big-screen :deep(*){box-sizing:border-box}.screen-header{height:58px;display:grid;grid-template-columns:1fr auto 1fr;align-items:center;border-bottom:1px solid #214861;position:relative}.screen-header::after{content:'';position:absolute;left:32%;right:32%;bottom:-1px;height:2px;background:#31c6dc;box-shadow:0 0 14px #31c6dc}.brand-lockup{display:flex;align-items:center;gap:10px;color:#31c6dc}.brand-lockup div{display:flex;flex-direction:column}.brand-lockup strong{font-size:13px}.brand-lockup span{margin-top:3px;color:#688da3;font:8px ui-monospace,monospace}.screen-title{font-size:21px;font-weight:750;color:#e8f7ff}.screen-clock{display:grid;grid-template-columns:auto 34px;justify-content:end;align-items:center;column-gap:12px}.screen-clock strong{font:18px ui-monospace,monospace;color:#7de8f5}.screen-clock span{grid-column:1;color:#6f94aa;font-size:9px;text-align:right}.screen-clock button{grid-column:2;grid-row:1/3;width:34px;height:34px;display:grid;place-items:center;color:#8bb3c7;background:#0d2c40;border:1px solid #27536d;border-radius:5px;cursor:pointer}.screen-kpis{height:74px;display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:9px;padding:9px 0}.screen-kpis>div{min-width:0;display:grid;grid-template-columns:1fr auto;align-content:center;padding:7px 10px;background:#0a2639;border:1px solid #1d4862;border-left:3px solid #31c6dc}.screen-kpis span{font-size:8px;color:#779cb0}.screen-kpis strong{grid-row:1/3;grid-column:2;font:23px ui-monospace,monospace;color:#dff8ff}.screen-kpis small{overflow:hidden;font:7px ui-monospace,monospace;color:#4e7489;text-overflow:ellipsis;white-space:nowrap}.screen-kpis .risk{border-left-color:#ff5869}.screen-kpis .risk strong{color:#ff7a87}.screen-grid{flex:1;min-height:0;display:grid;grid-template-columns:24% 52% 24%;grid-template-rows:minmax(0,1fr) clamp(180px,22vh,220px);gap:9px}.screen-column{min-width:0;min-height:0;display:grid;gap:9px}.left-column{grid-template-rows:.82fr 1fr .9fr}.right-column{grid-template-rows:1.2fr .9fr .9fr}.screen-panel>:deep(.base-chart){height:calc(100% - 34px);min-height:0}.platform-intro{height:calc(100% - 34px);display:flex;flex-direction:column;padding:9px 11px}.platform-intro p{margin:0;color:#86a8b9;font-size:8px;line-height:1.6}.capability-tags{display:flex;flex-wrap:wrap;gap:4px;margin-top:7px}.capability-tags span{padding:3px 5px;color:#7de8f5;background:rgba(49,198,220,.06);border:1px solid rgba(49,198,220,.2);font-size:7px}.platform-intro dl{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;margin:auto 0 0}.platform-intro dl>div{min-width:0;padding:5px 6px;background:#092335;border:1px solid rgba(37,80,107,.6)}.platform-intro dt{color:#52778b;font-size:7px}.platform-intro dd{margin:3px 0 0;color:#d9edf7;font:10px ui-monospace,monospace}.situation{grid-column:2;grid-row:1}.situation>:deep(.pipeline-stage){height:calc(100% - 34px)}.situation-foot{position:absolute;left:12px;right:12px;bottom:8px;display:flex;justify-content:center;gap:20px;color:#779cb0;font-size:7px;z-index:4}.situation-foot span{display:flex;align-items:center;gap:5px}.situation-foot i{width:6px;height:6px;border-radius:50%;background:#4ddeaa;box-shadow:0 0 8px #4ddeaa}.situation-foot i.cyan{background:#31c6dc}.situation-foot i.danger{background:#ff5869}.ticker{height:calc(100% - 34px);display:flex;flex-direction:column;padding:5px 9px;overflow:hidden}.ticker>div{min-width:0;min-height:25px;display:grid;grid-template-columns:52px 78px minmax(0,1fr);align-items:center;gap:6px;border-bottom:1px solid rgba(37,80,107,.45);font-size:7px}.ticker time{color:#557f95;font-family:ui-monospace,monospace}.ticker b{overflow:hidden;color:#ffb454;text-overflow:ellipsis;white-space:nowrap}.ticker b.high,.ticker b.critical{color:#ff6a78}.ticker span{color:#95b7c8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ticker code{grid-column:3;color:#52778b;text-align:right;font-size:6px}.engine-grid{height:calc(100% - 34px);display:grid;grid-template-columns:1fr 1fr;padding:5px 9px;gap:3px 9px}.engine-grid>div{min-width:0;display:grid;grid-template-columns:7px 1fr auto;align-content:center;column-gap:6px;border-bottom:1px solid rgba(37,80,107,.5)}.engine-grid i{width:6px;height:6px;margin-top:3px;border-radius:50%;background:#597c90}.engine-grid i.enabled,.engine-grid i.configured{background:#4ddeaa;box-shadow:0 0 8px #4ddeaa}.engine-grid i.standby{background:#ffb454}.engine-grid i.degraded{background:#ff5869}.engine-grid span{font-size:8px}.engine-grid strong{font-size:7px;color:#75cadd}.engine-grid small{grid-column:2/4;margin-top:2px;color:#52778b;font-size:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.screen-empty{height:calc(100% - 34px);display:grid;place-items:center;color:#52778b;font-size:8px}.samples-panel{grid-column:1/4;grid-row:2}.samples-panel>:deep(.sample-strip),.samples-panel>:deep(.sample-empty){height:calc(100% - 34px)}.screen-footer{height:27px;display:flex;align-items:center;gap:18px;color:#496f84;font:7px ui-monospace,monospace}.screen-footer span:nth-child(2){flex:1;text-align:center}.screen-footer strong{color:#7ea2b4;font-weight:500}.screen-footer>i{width:6px;height:6px;border-radius:50%;background:#31c6dc}.screen-state{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;color:#7da3b7}.screen-state button{height:34px;padding:0 14px;color:#071b2a;background:#31c6dc;border:0;border-radius:5px;cursor:pointer}.spin{animation:rotate .9s linear infinite}@keyframes rotate{to{transform:rotate(360deg)}}@media(max-aspect-ratio:1.45){.screen-grid{grid-template-columns:27% 46% 27%}.screen-title{font-size:18px}}
.screen-grid{grid-template-columns:minmax(0,24fr) minmax(0,52fr) minmax(0,24fr)}
@media(max-aspect-ratio:1.45){.screen-grid{grid-template-columns:minmax(0,27fr) minmax(0,46fr) minmax(0,27fr)}}
.big-screen{background-color:#041521;background-image:radial-gradient(ellipse at 50% 42%,rgba(15,105,135,.2),transparent 38%),linear-gradient(rgba(62,135,171,.075) 1px,transparent 1px),linear-gradient(90deg,rgba(62,135,171,.075) 1px,transparent 1px);box-shadow:inset 0 0 110px rgba(0,0,0,.5)}
.screen-kpis>div{background:linear-gradient(130deg,rgba(15,56,76,.9),rgba(5,29,43,.88));border-color:rgba(53,132,165,.7);clip-path:polygon(0 7px,7px 0,100% 0,100% calc(100% - 7px),calc(100% - 7px) 100%,0 100%)}
.platform-intro p{color:#9fc2d0}.platform-intro .intro-future{margin-top:5px;color:#6f9eb1;border-left:2px solid rgba(77,222,170,.7);padding-left:6px}.capability-tags span{color:#a1f4fb;background:rgba(49,198,220,.08);border-color:rgba(82,222,239,.35)}.platform-intro dl>div{background:linear-gradient(135deg,rgba(10,48,67,.8),rgba(6,28,42,.7));border-color:rgba(54,122,151,.65)}.platform-intro dd{color:#e4f8ff}
</style>
