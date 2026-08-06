<template>
  <div class="big-screen">
    <!-- 环境光层：星云 + 暗角，建立"深色空间"而非平涂深蓝 -->
    <div class="screen-ambient" aria-hidden="true"></div>

    <header class="screen-header">
      <div class="brand-lockup">
        <span class="brand-mark"><ShieldCheck :size="22" /></span>
        <div>
          <strong>AIGC 安全运营台</strong>
          <span>AIGC SECURITY OPERATIONS</span>
        </div>
      </div>

      <div class="title-lockup">
        <Decoration8 class="title-wing" :color="['#0a6ea8', '#2ac9ff']" />
        <h1 class="screen-title">
          AIGC 安全可视化驾驶舱
          <small>AI SECURITY COMMAND CENTER</small>
        </h1>
        <Decoration8 class="title-wing right" :color="['#0a6ea8', '#2ac9ff']" reverse />
      </div>

      <div class="screen-clock">
        <strong>{{ clock }}</strong>
        <span>{{ date }}</span>
        <button title="退出大屏" aria-label="退出大屏" @click="exitScreen"><Minimize2 :size="17" /></button>
      </div>
    </header>

    <div v-if="authRequired" class="screen-state">
      <LockKeyhole :size="28" /><strong>审核员会话已失效</strong>
      <button @click="openLogin">重新登录</button>
    </div>
    <div v-else-if="!data" class="screen-state">
      <LoaderCircle :size="28" class="spin" /><strong>{{ error || '正在汇聚安全数据' }}</strong>
    </div>

    <template v-else>
      <!-- 顶部 KPI：快速态势入口 -->
      <div class="screen-kpis">
        <CockpitMetric label="审核任务" :subtitle="`${data.window.hours}H WINDOW`" :value="data.summary.business_reviews"><template #icon><ClipboardCheck /></template></CockpitMetric>
        <CockpitMetric label="安全事件" subtitle="REAL INCIDENTS" :value="data.summary.total_events" tone="cyan"><template #icon><ShieldAlert /></template></CockpitMetric>
        <CockpitMetric label="风险告警" :subtitle="`BLOCKED ${data.summary.blocked}`" :value="data.summary.alerts" tone="red" :alert="data.summary.alerts > 0"><template #icon><Siren /></template></CockpitMetric>
        <CockpitMetric label="来源主体" subtitle="PUBLIC + INTERNAL" :value="data.summary.unique_clients" tone="mint"><template #icon><Network /></template></CockpitMetric>
        <CockpitMetric label="P95 延迟" :subtitle="`MS · 健康 ${latencyHealthScore(data.summary.p95_latency_ms)}`" :value="data.summary.p95_latency_ms" tone="violet"><template #icon><Gauge /></template></CockpitMetric>
        <CockpitMetric label="检测报告" :subtitle="`${data.reports.total} TOTAL`" :value="data.reports.in_window"><template #icon><FileCheck2 /></template></CockpitMetric>
      </div>
      <main class="screen-grid">
        <!-- 左列：平台定位 + 趋势 + 风险构成 -->
        <div class="screen-column left-column">
          <CockpitPanel class="intro-panel" title="平台简介" code="PLATFORM PROFILE">
            <div class="platform-intro">
              <p>平台不以“反 AI”为目标，而是把真实性、内容安全、来源凭证与人工复核编排为同一条审计链，识别伪造、风险与缺乏可追溯依据的自动化内容。</p>
              <p class="intro-future">红线知识库覆盖敏感内容、隐私、违法诱导和提示注入；可扩展搜索支撑的事实核验，将待验证主张送入审计队列。</p>
              <div class="capability-tags"><span>真实性审计</span><span>内容安全</span><span>大模型护栏</span><span>C2PA 溯源</span></div>
              <dl>
                <div><dt>公网来源</dt><dd>{{ sourceBreakdown.public }}</dd></div>
                <div><dt>内部 / 测试</dt><dd>{{ sourceBreakdown.internal }}</dd></div>
                <div><dt>原图公开</dt><dd>否</dd></div>
              </dl>
            </div>
          </CockpitPanel>
          <CockpitPanel class="trend" title="审核与告警趋势" code="EVENT TREND" tone="cyan" flush>
            <BaseChart :option="trendOption" aria-label="大屏审核与告警趋势图" dark />
          </CockpitPanel>
          <CockpitPanel class="ring" title="风险类别分布" code="RISK PROFILE" tone="violet" flush>
            <BaseChart :option="riskOption" aria-label="大屏风险类别环形图" dark />
          </CockpitPanel>
        </div>

        <!-- 中央：第一视觉焦点 -->
        <CockpitPanel class="situation" title="多模态审核防御链" code="DEFENSE PIPELINE" focus flush>
          <template #meta>
            <span class="situation-badge"><i aria-hidden="true"></i>实时运行</span>
          </template>
          <SecurityPipeline
            :configured="data.service_health.configured_models"
            :total="data.service_health.total_models"
            :alert="data.service_health.audit_chain !== 'healthy'"
          />
          <div class="situation-foot">
            <span><i></i>主系统在线</span>
            <span><i class="cyan"></i>{{ data.service_health.configured_models }}/{{ data.service_health.total_models }} 引擎就绪</span>
            <span><i :class="{ danger: data.service_health.audit_chain !== 'healthy' }"></i>审计链{{ data.service_health.audit_chain === 'healthy' ? '完整' : '异常' }}</span>
          </div>
        </CockpitPanel>

        <!-- 右列：告警流 + 能力态势 + 引擎 -->
        <div class="screen-column right-column">
          <CockpitPanel class="alerts" title="实时风险事件" code="LIVE ALERTS" :tone="data.recent_alerts.length ? 'danger' : 'blue'" flush>
            <div v-if="data.recent_alerts.length" class="ticker">
              <div v-for="alert in data.recent_alerts.slice(0, 7)" :key="alert.id" class="ticker-row">
                <time>{{ formatTime(alert.occurred_at) }}</time>
                <b :class="alert.severity">{{ alert.risk_code || alert.module }}</b>
                <span>{{ alert.summary }}</span>
                <code>{{ sourceLabel(alert.client_ip) }}</code>
              </div>
            </div>
            <div v-else class="screen-empty">当前窗口暂无风险告警</div>
          </CockpitPanel>
          <CockpitPanel class="radar" title="防护能力态势" code="CAPABILITY POSTURE" tone="cyan" flush>
            <BaseChart :option="radarOption" aria-label="防护能力雷达图" dark suppress-tooltip />
          </CockpitPanel>
          <CockpitPanel class="engines" title="模型与引擎" code="ENGINE STATUS" flush>
            <div class="engine-grid">
              <div v-for="model in data.models.slice(0, 8)" :key="model.id" class="engine-row">
                <i :class="model.status"></i>
                <span>{{ model.label }}</span>
                <strong :class="model.status">{{ statusLabel(model.status) }}</strong>
                <small>{{ model.model }}</small>
              </div>
            </div>
          </CockpitPanel>
        </div>

        <!-- 底部：业务闭环展示 -->
        <CockpitPanel class="samples-panel" title="典型风险样本实测" code="CURATED BENCHMARK · SANITIZED" flush>
          <RiskSampleStrip :samples="demoSamples" />
        </CockpitPanel>
      </main>

      <footer class="screen-footer">
        <span>数据窗口 {{ data.window.start }} → {{ data.window.end }}</span>
        <span>样本：合成演示 / 公开夹具 / 授权仓库 · 敏感图已脱敏</span>
        <strong>原始提示词与危险输出：AES-GCM 加密留存</strong>
        <i :class="{ spin: loading }" :title="loading ? '正在刷新' : '数据已同步'"></i>
      </footer>
    </template>
    <LoginDialog :open="loginOpen" @close="loginOpen = false" />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { EChartsCoreOption } from 'echarts/core'
import { Decoration8 } from '@kjgl77/datav-vue3'
import { ClipboardCheck, FileCheck2, Gauge, LoaderCircle, LockKeyhole, Minimize2, Network, ShieldAlert, ShieldCheck, Siren } from 'lucide-vue-next'
import BaseChart from '../components/dashboard/BaseChart.vue'
import CockpitMetric from '../components/dashboard/CockpitMetric.vue'
import LoginDialog from '../components/auth/LoginDialog.vue'
import CockpitPanel from '../components/dashboard/CockpitPanel.vue'
import RiskSampleStrip, { type DemoRiskSample } from '../components/dashboard/RiskSampleStrip.vue'
import SecurityPipeline from '../components/dashboard/SecurityPipeline.vue'
import { useDashboard } from '../composables/useDashboard'
import { alpha, areaGradient, axisBase, categoryColor, token, tooltipBase } from '../lib/screenTheme'
import '../styles/screen-tokens.css'

const router = useRouter()
const { data, loading, error, authRequired } = useDashboard()
const now = ref(new Date())
const demoSamples = ref<DemoRiskSample[]>([])
const loginOpen = ref(false)
let clockTimer: ReturnType<typeof setInterval> | null = null
let sampleController: AbortController | null = null
const clock = computed(() => now.value.toLocaleTimeString('zh-CN', { hour12: false }))
const date = computed(() => now.value.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', weekday: 'short' }))
const categoryNames: Record<string, string> = { jailbreak: '越狱攻击', prompt_injection: '提示词注入', cyber_abuse: '网络攻击滥用', weapons_violence: '武器暴力', self_harm: '自伤风险', sexual_content: '色情内容', child_safety: '未成年人安全', personal_data: '隐私数据', illegal_activity: '违法活动', agent_security: 'Agent 安全', adult_content: '成人内容', weapon_display: '武器展示', graphic_violence: '暴力血腥', political_sensitive: '政治敏感', marketing_violation: '营销违规', policy_violation: '策略违规', sensitive_data: '敏感数据', unsafe: '不安全内容', misinformation: '虚假信息', hate_speech: '仇恨言论' }

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

/** 趋势图：发光折线 + 面积渐变 + 异常点强调 */
const trendOption = computed<EChartsCoreOption>(() => {
  const accent = token('--sc-accent')
  const danger = token('--sc-critical')
  const timeline = data.value?.timeline || []
  const alerts = timeline.map(item => item.alerts)
  const peak = Math.max(0, ...alerts)
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', confine: true, ...tooltipBase(), axisPointer: { type: 'line', lineStyle: { color: alpha(accent, .5), type: 'dashed' } } },
    legend: { data: ['审核任务', '风险告警'], right: 10, top: 4, itemWidth: 12, itemHeight: 3, itemGap: 14, textStyle: { color: token('--sc-ink-3'), fontSize: 11 } },
    grid: { left: 8, right: 12, top: 30, bottom: 6, containLabel: true },
    xAxis: { type: 'category', boundaryGap: false, data: timeline.map(item => new Date(item.start).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })), ...axisBase(), splitLine: { show: false } },
    yAxis: { type: 'value', minInterval: 1, ...axisBase(), axisLine: { show: false }, splitLine: { lineStyle: { color: token('--sc-line-soft'), type: 'dashed' } } },
    series: [
      {
        name: '审核任务', type: 'line', smooth: .34, showSymbol: false, symbolSize: 7,
        lineStyle: { color: accent, width: 2.4, shadowColor: alpha(accent, .7), shadowBlur: 12, shadowOffsetY: 2 },
        itemStyle: { color: accent, borderColor: '#eafcff', borderWidth: 1.5 },
        areaStyle: { color: areaGradient(accent, .34) },
        emphasis: { focus: 'series' },
        data: timeline.map(item => item.events),
      },
      {
        name: '风险告警', type: 'line', smooth: .34, showSymbol: false, symbolSize: 7,
        lineStyle: { color: danger, width: 2, shadowColor: alpha(danger, .68), shadowBlur: 12 },
        itemStyle: { color: danger, borderColor: '#fff0f3', borderWidth: 1.5 },
        areaStyle: { color: areaGradient(danger, .20) },
        // 峰值告警点单独标出，运营人员一眼看到异常时刻
        markPoint: peak > 0 ? { symbolSize: 42, data: [{ type: 'max', name: '峰值' }], itemStyle: { color: alpha(danger, .9) }, label: { color: '#fff', fontSize: 10, fontWeight: 700 } } : undefined,
        data: alerts,
      },
    ],
  }
})

/** 风险环形图：颜色本身承载危害等级，并显示占比标签 */
const riskOption = computed<EChartsCoreOption>(() => {
  const items = data.value?.risk_distribution || []
  const total = items.reduce((sum, item) => sum + item.value, 0)
  const seeded = items.map((item, index) => ({
    ...item,
    itemStyle: { color: categoryColor(item.name, index), borderColor: 'rgba(3,16,31,.85)', borderWidth: 2 },
  }))
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item', confine: true, ...tooltipBase(),
      formatter: (params: { name: string; value: number; percent: number }) =>
        `${categoryNames[params.name] || params.name}<br/><b style="color:${token('--sc-ink')}">${params.value}</b> 次 · ${params.percent}%`,
    },
    legend: {
      type: 'scroll', orient: 'vertical', right: 4, top: 'middle', height: '86%', width: '48%',
      itemGap: 9, selectedMode: false, pageIconSize: 8, pageIconColor: token('--sc-accent'), pageIconInactiveColor: token('--sc-ink-4'),
      pageTextStyle: { color: token('--sc-ink-4'), fontSize: 10 },
      // 中文类别名最长 7 字（约 84px）+ 百分比，给足宽度避免截断成 "policy_violation ..."
      textStyle: { color: token('--sc-ink-2'), fontSize: 11, overflow: 'truncate', width: 132 },
      itemWidth: 9, itemHeight: 9,
      formatter: (name: string) => {
        const hit = items.find(item => item.name === name)
        const label = categoryNames[name] || name
        if (!hit || !total) return label
        return `${label}  ${Math.round((hit.value / total) * 1000) / 10}%`
      },
    },
    series: [{
      type: 'pie', radius: ['46%', '68%'], center: ['26%', '52%'],
      label: { show: false }, labelLine: { show: false },
      itemStyle: { borderRadius: 3 },
      emphasis: { scale: true, scaleSize: 5, itemStyle: { shadowBlur: 18, shadowColor: alpha(token('--sc-accent'), .5) } },
      data: seeded.length ? seeded : [{ name: '无风险事件', value: 1, itemStyle: { color: 'rgba(36,77,104,.7)' } }],
    }],
  }
})

function latencyHealthScore(p95LatencyMs: number) {
  const healthyMs = 5_000
  const criticalMs = 60_000
  if (p95LatencyMs <= healthyMs) return 100
  if (p95LatencyMs >= criticalMs) return 0
  return Math.round(100 * (criticalMs - p95LatencyMs) / (criticalMs - healthyMs))
}

/** 能力雷达：双层填充 + 顶点高亮 */
const radarOption = computed<EChartsCoreOption>(() => {
  const summary = data.value?.summary
  const models = data.value?.service_health
  const accent = token('--sc-accent')
  const cyan = token('--sc-cyan')
  const incidentHandled = summary?.alerts ? Math.min(100, Math.round((summary.blocked / summary.alerts) * 100)) : 100
  const latencyHealth = summary ? latencyHealthScore(summary.p95_latency_ms) : 0
  return {
    // 驾驶舱的视觉层级是固定的：雷达 hover 卡片在这里不可操作，
    // 且会在紧凑屏上溢出到引擎面板。
    backgroundColor: 'transparent',
    tooltip: { show: false, triggerOn: 'none', appendToBody: false, alwaysShowContent: false },
    radar: {
      radius: '64%', center: ['50%', '54%'],
      indicator: [{ name: '成功率', max: 100 }, { name: '响应速度', max: 100 }, { name: '风险处置', max: 100 }, { name: '审计完整性', max: 100 }, { name: '引擎就绪性', max: 100 }],
      axisName: { color: token('--sc-ink-2'), fontSize: 11 },
      splitArea: { areaStyle: { color: [alpha(accent, .015), alpha(accent, .06)] } },
      splitLine: { lineStyle: { color: token('--sc-line-soft') } },
      axisLine: { lineStyle: { color: token('--sc-line-2') } },
    },
    series: [{
      type: 'radar',
      symbolSize: 5,
      data: [{
        value: [summary?.success_rate || 0, latencyHealth, incidentHandled, data.value?.service_health.audit_chain === 'healthy' ? 100 : 0, models ? Math.round(models.configured_models / models.total_models * 100) : 0],
        areaStyle: { color: { type: 'radial', x: .5, y: .5, r: .7, colorStops: [{ offset: 0, color: alpha(cyan, .06) }, { offset: 1, color: alpha(accent, .30) }] } },
        lineStyle: { color: accent, width: 2.2, shadowColor: alpha(accent, .7), shadowBlur: 12 },
        itemStyle: { color: '#eafcff', borderColor: accent, borderWidth: 2 },
      }],
    }],
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
:global(body:has(.big-screen)){overflow:hidden}

/* ========== 1. 舞台与环境光 ========== */
.big-screen{
  position:fixed;inset:0;z-index:500;
  display:flex;flex-direction:column;
  min-width:1024px;min-height:640px;
  box-sizing:border-box;
  padding:12px 16px 8px;
  color:var(--sc-ink-2);
  font-family:var(--sc-font);
  /* 平涂深蓝换成"深色空间"：底色 + 网格，星云交给 .screen-ambient */
  background-color:var(--sc-space);
  background-image:
    linear-gradient(var(--sc-grid) 1px,transparent 1px),
    linear-gradient(90deg,var(--sc-grid) 1px,transparent 1px);
  background-size:58px 58px,58px 58px;
}
.big-screen :deep(*){box-sizing:border-box}

/* 三色星云 + 四角暗角：让中央亮、四周沉，形成视觉重心 */
.screen-ambient{
  position:absolute;inset:0;z-index:0;pointer-events:none;
  background:
    radial-gradient(ellipse 46% 40% at 50% 42%,var(--sc-nebula),transparent 68%),
    radial-gradient(ellipse 34% 32% at 12% 76%,var(--sc-nebula-2),transparent 66%),
    radial-gradient(ellipse 32% 30% at 88% 22%,var(--sc-nebula-3),transparent 66%),
    radial-gradient(ellipse 78% 70% at 50% 50%,transparent 42%,var(--sc-void) 100%);
}
.big-screen>*:not(.screen-ambient){position:relative;z-index:1}

/* ========== 2. 顶栏 ========== */
.screen-header{
  flex:none;height:70px;
  display:grid;grid-template-columns:1fr auto 1fr;align-items:center;
  border-bottom:1px solid var(--sc-line-soft);
}
/* 中段高亮的底边线，把视线导向标题 */
.screen-header::after{
  content:'';position:absolute;left:28%;right:28%;bottom:-1px;height:2px;
  background:linear-gradient(90deg,transparent,var(--sc-accent) 22%,#bff0ff 50%,var(--sc-accent) 78%,transparent);
  box-shadow:0 0 18px rgba(42,201,255,.62);
}
.brand-lockup{display:flex;align-items:center;gap:12px}
.brand-mark{
  width:40px;height:40px;flex:none;
  display:grid;place-items:center;
  border-radius:var(--sc-radius-sm);
  color:#dff7ff;
  background:linear-gradient(148deg,rgba(42,201,255,.30),rgba(10,110,168,.14));
  border:1px solid rgba(112,224,255,.40);
  box-shadow:var(--sc-glow-1),var(--sc-inset);
}
.brand-lockup div{display:flex;flex-direction:column;gap:4px}
.brand-lockup strong{
  color:var(--sc-ink);
  font-size:var(--sc-fs-title);
  font-weight:var(--sc-w-title);
  letter-spacing:.02em;
}
.brand-lockup span{
  color:var(--sc-ink-4);
  font-family:var(--sc-font-mono);
  font-size:var(--sc-fs-code);
  letter-spacing:.14em;
}

.title-lockup{
  position:relative;width:min(760px,50vw);
  display:grid;grid-template-columns:minmax(48px,1fr) auto minmax(48px,1fr);
  align-items:center;gap:16px;
}
.title-wing{width:100%;height:18px;opacity:.85}
.title-wing.right{transform:scaleY(-1)}
/* 主标题：全屏最强文字 */
.screen-title{
  margin:0;
  display:flex;flex-direction:column;align-items:center;
  color:var(--sc-ink);
  font-size:var(--sc-fs-hero);
  font-weight:var(--sc-w-hero);
  letter-spacing:var(--sc-ls-hero);
  white-space:nowrap;
  text-shadow:0 0 26px rgba(42,201,255,.38);
}
.screen-title small{
  margin-top:6px;
  color:var(--sc-ink-3);
  font-family:var(--sc-font-mono);
  font-size:var(--sc-fs-code);
  font-weight:400;
  letter-spacing:var(--sc-ls-code);
}

.screen-clock{
  display:grid;grid-template-columns:auto 36px;
  justify-content:end;align-items:center;column-gap:14px;
}
.screen-clock strong{
  color:#c9f4ff;
  font-family:var(--sc-font-num);
  font-size:clamp(19px,1.32vw,26px);
  font-weight:600;
  font-variant-numeric:tabular-nums;
  letter-spacing:.03em;
  text-shadow:var(--sc-text-glow);
}
.screen-clock span{
  grid-column:1;
  color:var(--sc-ink-3);
  font-size:var(--sc-fs-aux);
  text-align:right;
}
.screen-clock button{
  grid-column:2;grid-row:1/3;
  width:36px;height:36px;
  display:grid;place-items:center;
  color:var(--sc-ink-3);
  background:rgba(10,40,66,.7);
  border:1px solid var(--sc-line-2);
  border-radius:var(--sc-radius-sm);
  cursor:pointer;
  transition:color var(--sc-t-fast),border-color var(--sc-t-fast),box-shadow var(--sc-t-fast);
}
.screen-clock button:hover{
  color:var(--sc-ink);
  border-color:var(--sc-line-hi);
  box-shadow:var(--sc-glow-1);
}

/* ========== 3. KPI 区 ========== */
.screen-kpis{
  flex:none;height:88px;
  display:grid;grid-template-columns:repeat(6,minmax(0,1fr));
  gap:var(--sc-gap);
  padding:var(--sc-gap) 0;
}

/* ========== 4. 主网格 ==========
   中列 52% 保证中枢是最大面板；行高把底部样本条固定在合理比例。 */
.screen-grid{
  flex:1;min-height:0;
  display:grid;
  grid-template-columns:minmax(0,24fr) minmax(0,52fr) minmax(0,24fr);
  grid-template-rows:minmax(0,1fr) clamp(206px,23vh,248px);
  gap:var(--sc-gap);
}
.screen-column{min-width:0;min-height:0;display:grid;gap:var(--sc-gap)}
.left-column{grid-template-rows:.84fr 1fr .92fr}
.right-column{grid-template-rows:1.2fr .9fr .92fr}
.situation{grid-column:2;grid-row:1}
.samples-panel{grid-column:1/4;grid-row:2}

/* 面板内容默认撑满：CockpitPanel 用 flex 布局，图表不再需要 calc 补偿标题高度 */
.screen-grid :deep(.base-chart){flex:1;min-height:0;height:auto}
.screen-grid :deep(.sample-strip),.screen-grid :deep(.sample-empty){flex:1;min-height:0}

/* ========== 5. 平台简介 ========== */
/* 简介是三段可变高度内容（正文 + 标签 + 数据），面板高度由网格分配。
   正文用 line-clamp 收口：空间不足时整行省略，而不是被面板裁掉半行文字。 */
.platform-intro{flex:1;min-height:0;display:flex;flex-direction:column;overflow:hidden}
.platform-intro p{
  margin:0;min-height:0;
  color:var(--sc-ink-2);
  font-size:var(--sc-fs-aux);
  line-height:1.72;
  display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;overflow:hidden;
}
.platform-intro .intro-future{
  flex:none;margin-top:8px;padding-left:9px;
  color:var(--sc-ink-3);
  border-left:2px solid rgba(60,232,170,.6);
  -webkit-line-clamp:2;
}
.capability-tags{flex:none;display:flex;flex-wrap:wrap;gap:6px;margin-top:10px;overflow:hidden;max-height:26px}
.capability-tags span{
  padding:4px 9px;border-radius:20px;
  color:#a8f0ff;
  background:var(--sc-accent-soft);
  border:1px solid rgba(112,224,255,.32);
  font-size:var(--sc-fs-code);
  letter-spacing:.02em;
}
.platform-intro dl{
  flex:none;
  display:grid;grid-template-columns:repeat(3,minmax(0,1fr));
  gap:8px;margin:auto 0 0;
}
.platform-intro dl>div{
  min-width:0;padding:8px 9px;
  border-radius:var(--sc-radius-sm);
  background:linear-gradient(140deg,rgba(12,52,80,.8),rgba(6,26,44,.6));
  border:1px solid var(--sc-line-soft);
}
.platform-intro dt{color:var(--sc-ink-4);font-size:var(--sc-fs-code)}
.platform-intro dd{
  margin:5px 0 0;
  color:var(--sc-ink);
  font-family:var(--sc-font-num);
  font-size:var(--sc-fs-body);
  font-weight:600;
}

/* ========== 6. 中枢面板 ========== */
.situation{overflow:hidden}
.situation-badge{
  display:inline-flex;align-items:center;gap:6px;
  margin-left:12px;padding:3px 9px;border-radius:20px;
  color:var(--sc-mint);
  background:var(--sc-mint-soft);
  border:1px solid rgba(60,232,170,.36);
  font-family:var(--sc-font-mono);
  font-size:var(--sc-fs-code);
  white-space:nowrap;
}
.situation-badge i{
  width:5px;height:5px;border-radius:50%;
  background:currentColor;box-shadow:0 0 7px currentColor;
  animation:live-blink 2s ease-in-out infinite;
}
@keyframes live-blink{0%,100%{opacity:1}50%{opacity:.35}}
.situation-foot{
  position:absolute;left:14px;right:14px;bottom:9px;z-index:5;
  display:flex;justify-content:center;gap:26px;
  color:var(--sc-ink-3);
  font-size:var(--sc-fs-code);
}
.situation-foot span{display:flex;align-items:center;gap:6px}
.situation-foot i{
  width:7px;height:7px;border-radius:50%;
  background:var(--sc-mint);box-shadow:var(--sc-glow-mint);
}
.situation-foot i.cyan{background:var(--sc-cyan);box-shadow:0 0 10px var(--sc-cyan)}
.situation-foot i.danger{background:var(--sc-danger);box-shadow:var(--sc-glow-danger)}

/* ========== 7. 告警流 ========== */
.ticker{flex:1;min-height:0;display:flex;flex-direction:column;padding:6px 13px;overflow:hidden}
/* 告警行数由数据决定，高度由面板分配：min-height 会让行数多时溢出面板，
   所以只给 flex 基准 + 上限，让行在空间不足时等比压缩而非顶出容器。 */
.ticker-row{
  min-width:0;flex:1 1 0;min-height:0;max-height:34px;
  display:grid;grid-template-columns:64px 92px minmax(0,1fr) auto;
  align-items:center;gap:9px;
  padding:2px 0;
  border-bottom:1px solid var(--sc-line-soft);
  font-size:var(--sc-fs-aux);
  overflow:hidden;
}
.ticker-row:last-child{border-bottom:0}
.ticker time{color:var(--sc-ink-3);font-family:var(--sc-font-mono);font-variant-numeric:tabular-nums}
/* 告警等级用语义色胶囊，不只是文字变色 */
.ticker b{
  overflow:hidden;
  padding:2px 7px;border-radius:4px;
  color:var(--sc-medium);
  background:var(--sc-medium-soft);
  font-size:var(--sc-fs-code);
  font-weight:600;
  text-align:center;
  text-overflow:ellipsis;white-space:nowrap;
}
.ticker b.high,.ticker b.critical{color:var(--sc-critical);background:var(--sc-danger-soft)}
.ticker span{color:var(--sc-ink-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
/* 来源 IP 独占第 4 列：此前挤在第 3 列会把行撑成两行，把面板顶开 */
.ticker code{
  grid-column:4;max-width:104px;
  color:var(--sc-ink-4);
  font-family:var(--sc-font-mono);
  font-size:var(--sc-fs-code);
  text-align:right;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}

/* ========== 8. 引擎列表 ========== */
.engine-grid{
  flex:1;min-height:0;
  display:grid;grid-template-columns:1fr 1fr;
  padding:6px 13px;gap:3px 14px;
}
.engine-row{
  min-width:0;
  display:grid;grid-template-columns:8px 1fr auto;
  align-content:center;column-gap:8px;
  border-bottom:1px solid var(--sc-line-soft);
}
/* 状态点：运行态带呼吸，读作"活的" */
.engine-grid i{
  width:7px;height:7px;margin-top:4px;
  border-radius:50%;background:var(--sc-ink-4);
}
.engine-grid i.enabled,.engine-grid i.configured{
  background:var(--sc-mint);box-shadow:var(--sc-glow-mint);
  animation:live-blink 2.8s ease-in-out infinite;
}
.engine-grid i.standby{background:var(--sc-medium);box-shadow:0 0 9px rgba(255,181,69,.5)}
.engine-grid i.degraded{background:var(--sc-danger);box-shadow:var(--sc-glow-danger)}
.engine-grid span{color:var(--sc-ink-2);font-size:var(--sc-fs-aux)}
.engine-grid strong{color:var(--sc-ink-3);font-size:var(--sc-fs-code);font-weight:600}
.engine-grid strong.enabled,.engine-grid strong.configured{color:var(--sc-mint)}
.engine-grid strong.degraded{color:var(--sc-danger)}
.engine-grid strong.standby{color:var(--sc-medium)}
.engine-grid small{
  grid-column:2/4;margin-top:2px;
  color:var(--sc-ink-4);
  font-family:var(--sc-font-mono);
  font-size:var(--sc-fs-code);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}

.screen-empty{
  flex:1;display:grid;place-items:center;
  color:var(--sc-ink-4);font-size:var(--sc-fs-aux);
}

/* ========== 9. 页脚 ========== */
.screen-footer{
  flex:none;height:30px;
  display:flex;align-items:center;gap:18px;
  color:var(--sc-ink-4);
  font-family:var(--sc-font-mono);
  font-size:var(--sc-fs-code);
}
.screen-footer span:nth-child(2){flex:1;text-align:center}
.screen-footer strong{color:var(--sc-ink-3);font-weight:400}
.screen-footer>i{
  width:7px;height:7px;flex:none;border-radius:50%;
  background:var(--sc-mint);box-shadow:var(--sc-glow-mint);
}
.screen-footer>i.spin{background:var(--sc-accent);box-shadow:var(--sc-glow-1);animation:live-blink 1s ease-in-out infinite}

/* ========== 10. 状态页 ========== */
.screen-state{
  flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;
  color:var(--sc-ink-3);
}
.screen-state strong{color:var(--sc-ink);font-size:var(--sc-fs-title)}
.screen-state button{
  height:38px;padding:0 18px;
  color:#04182b;
  background:linear-gradient(140deg,#7fe6ff,var(--sc-accent));
  border:0;border-radius:var(--sc-radius-sm);
  font-size:var(--sc-fs-body);font-weight:600;
  cursor:pointer;
  box-shadow:var(--sc-glow-2);
}
.spin{animation:rotate .9s linear infinite}
@keyframes rotate{to{transform:rotate(360deg)}}

/* ========== 11. 响应式 ========== */
@media(max-aspect-ratio:1.45){
  .screen-grid{grid-template-columns:minmax(0,27fr) minmax(0,46fr) minmax(0,27fr)}
}
/* 简介面板在 ≤900px 高时只有约 70px 内容区，放不下"正文+延伸说明+标签+数据"四段。
   延伸说明是可选阅读内容，优先让位给标签与统计数字。 */
@media(max-height:900px){
  .platform-intro .intro-future{display:none}
  .platform-intro p{-webkit-line-clamp:2;line-height:1.6}
  .capability-tags{margin-top:6px;gap:5px}
  .platform-intro dl{gap:6px}
  .platform-intro dl>div{padding:6px 8px}
  .platform-intro dd{margin-top:3px}
}
@media(max-height:820px){
  .screen-header{height:62px}
  .screen-kpis{height:80px;padding:10px 0}
  .screen-grid{gap:10px;grid-template-rows:minmax(0,1fr) clamp(190px,22vh,224px)}
  .screen-column{gap:10px}
}
@media(max-height:700px){
  .big-screen{padding:8px 12px 6px}
  .screen-header{height:56px}
  .screen-kpis{height:72px;padding:8px 0}
  .platform-intro .intro-future{display:none}
  .situation-foot{gap:16px}
}
@media(max-width:1199px){
  .big-screen{padding:8px 10px 6px}
  .screen-grid{gap:9px;grid-template-columns:minmax(0,25fr) minmax(0,50fr) minmax(0,25fr);grid-template-rows:minmax(0,1fr) 184px}
  .screen-column{gap:9px}
  .left-column{grid-template-rows:.76fr 1fr .9fr}
  .screen-kpis{gap:9px;height:70px}
  .title-lockup{width:440px;gap:10px}
  .title-wing{height:14px}
  .platform-intro .intro-future{display:none}
  .ticker-row{grid-template-columns:52px 74px minmax(0,1fr);gap:6px}
  .engine-grid{padding:5px 9px;gap:2px 9px}
  .situation-foot{display:none}
}
</style>
