<template>
  <div class="big-screen">
    <header class="screen-header">
      <div class="brand-lockup"><ShieldCheck :size="24" /><div><strong>AIGC 安全运营台</strong><span>全域内容安全态势</span></div></div>
      <div class="screen-title">AIGC 安全可视化驾驶舱</div>
      <div class="screen-clock"><strong>{{ clock }}</strong><span>{{ date }}</span><button title="退出大屏" @click="exitScreen"><Minimize2 :size="17" /></button></div>
    </header>

    <div v-if="authRequired" class="screen-state"><LockKeyhole :size="28" /><strong>审核员会话已失效</strong><button @click="openLogin">重新登录</button></div>
    <div v-else-if="!data" class="screen-state"><LoaderCircle :size="28" class="spin" /><strong>{{ error || '正在汇聚安全数据' }}</strong></div>
    <template v-else>
      <div class="screen-kpis">
        <div><span>审核任务</span><strong>{{ data.summary.business_reviews }}</strong><small>{{ data.window.hours }}H</small></div>
        <div><span>安全事件</span><strong>{{ data.summary.total_events }}</strong><small>REAL DATA</small></div>
        <div class="risk"><span>风险告警</span><strong>{{ data.summary.alerts }}</strong><small>{{ data.summary.block_rate }}%</small></div>
        <div><span>来源节点</span><strong>{{ data.summary.unique_clients }}</strong><small>IP</small></div>
        <div><span>P95 延迟</span><strong>{{ data.summary.p95_latency_ms }}</strong><small>MS</small></div>
        <div><span>检测报告</span><strong>{{ data.reports.in_window }}</strong><small>{{ data.reports.total }} TOTAL</small></div>
      </div>

      <main class="screen-grid">
        <div class="screen-column left-column">
          <section class="screen-panel trend"><PanelTitle title="审核趋势" code="EVENT TREND" /><BaseChart :option="trendOption" aria-label="大屏审核趋势图" dark /></section>
          <section class="screen-panel ring"><PanelTitle title="风险分布" code="RISK PROFILE" /><BaseChart :option="riskOption" aria-label="大屏风险环形图" dark /></section>
        </div>

        <section class="screen-panel situation">
          <PanelTitle title="来源节点态势" code="SOURCE TOPOLOGY" />
          <BaseChart :option="situationOption" aria-label="来源节点世界地图与拓扑图" dark />
          <div class="topology-note">节点采用拓扑布局，不推断 IP 地理位置</div>
          <div class="situation-foot"><span><i></i>主系统在线</span><span><i class="cyan"></i>{{ data.service_health.configured_models }}/{{ data.service_health.total_models }} 引擎就绪</span><span><i :class="{ danger: data.service_health.audit_chain !== 'healthy' }"></i>审计链{{ data.service_health.audit_chain === 'healthy' ? '完整' : '异常' }}</span></div>
        </section>

        <div class="screen-column right-column">
          <section class="screen-panel radar"><PanelTitle title="防护能力态势" code="CONTROL POSTURE" /><BaseChart :option="radarOption" aria-label="防护能力雷达图" dark /></section>
          <section class="screen-panel engines"><PanelTitle title="模型与引擎" code="ENGINE STATUS" /><div class="engine-grid"><div v-for="model in data.models" :key="model.id"><i :class="model.status"></i><span>{{ model.label }}</span><strong>{{ statusLabel(model.status) }}</strong><small>{{ model.model }}</small></div></div></section>
        </div>

        <section class="screen-panel alerts"><PanelTitle title="实时风险事件" code="LIVE ALERTS" /><div v-if="data.recent_alerts.length" class="ticker"><div v-for="alert in data.recent_alerts.slice(0, 8)" :key="alert.id"><time>{{ formatTime(alert.occurred_at) }}</time><b :class="alert.severity">{{ alert.risk_code || alert.module }}</b><span>{{ alert.summary }}</span><code>{{ alert.client_ip || 'internal' }}</code></div></div><div v-else class="screen-empty">当前窗口暂无风险告警</div></section>
      </main>
      <footer class="screen-footer"><span>数据窗口 {{ data.window.start }} → {{ data.window.end }}</span><span>{{ data.data_sources.join(' · ') }}</span><strong>原始提示词与危险输出：AES-GCM 加密留存</strong><i :class="{ spin: loading }"></i></footer>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { registerMap, type EChartsCoreOption } from 'echarts/core'
import { LoaderCircle, LockKeyhole, Minimize2, ShieldCheck } from 'lucide-vue-next'
import BaseChart from '../components/dashboard/BaseChart.vue'
import { useDashboard } from '../composables/useDashboard'
import worldMap from '../assets/world.json'

registerMap('aigc-world', worldMap as never)
const PanelTitle = defineComponent({ props: { title: String, code: String }, setup: props => () => h('header', { class: 'panel-title' }, [h('strong', props.title), h('span', props.code)]) })
const router = useRouter()
const { data, loading, error, authRequired, openLogin } = useDashboard()
const now = ref(new Date())
let clockTimer: ReturnType<typeof setInterval> | null = null
const clock = computed(() => now.value.toLocaleTimeString('zh-CN', { hour12: false }))
const date = computed(() => now.value.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', weekday: 'short' }))
const riskColors = ['#ff5869', '#ffb454', '#31c6dc', '#4ddeaa', '#9b8cff', '#8fa8b8']

const trendOption = computed<EChartsCoreOption>(() => ({
  backgroundColor: 'transparent', tooltip: { trigger: 'axis' },
  grid: { left: 36, right: 12, top: 24, bottom: 24 },
  xAxis: { type: 'category', boundaryGap: false, data: data.value?.timeline.map(item => new Date(item.start).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })) || [], axisLine: { lineStyle: { color: '#244d68' } }, axisLabel: { color: '#6f94aa', fontSize: 8 } },
  yAxis: { type: 'value', minInterval: 1, axisLabel: { color: '#6f94aa', fontSize: 8 }, splitLine: { lineStyle: { color: 'rgba(64,132,169,.15)' } } },
  series: [
    { type: 'line', smooth: true, showSymbol: false, lineStyle: { color: '#31c6dc', width: 2 }, areaStyle: { color: 'rgba(49,198,220,.10)' }, data: data.value?.timeline.map(item => item.events) || [] },
    { type: 'line', smooth: true, showSymbol: false, lineStyle: { color: '#ff5869', width: 1.5 }, data: data.value?.timeline.map(item => item.alerts) || [] },
  ],
}))
const riskOption = computed<EChartsCoreOption>(() => ({
  backgroundColor: 'transparent', tooltip: { trigger: 'item' }, color: riskColors,
  legend: { bottom: 0, textStyle: { color: '#7fa2b6', fontSize: 8 }, itemWidth: 8, itemHeight: 8 },
  series: [{ type: 'pie', radius: ['48%', '70%'], center: ['50%', '42%'], label: { show: false }, data: data.value?.risk_distribution.length ? data.value.risk_distribution : [{ name: '无风险事件', value: 1, itemStyle: { color: '#244d68' } }] }],
}))
const situationOption = computed<EChartsCoreOption>(() => {
  const sources = data.value?.top_sources || []
  const nodes = [{ id: 'platform', name: 'AIGC 安全运营台', symbolSize: 58, itemStyle: { color: '#31c6dc', shadowBlur: 28, shadowColor: '#31c6dc' }, label: { show: true, color: '#e8f7ff', fontSize: 10 } }, ...sources.map((source, index) => ({ id: `source-${index}`, name: source.client_ip, value: source.events, symbolSize: Math.min(38, 16 + source.events * 2), itemStyle: { color: source.alerts ? '#ff5869' : '#4ddeaa', shadowBlur: 12, shadowColor: source.alerts ? '#ff5869' : '#4ddeaa' }, label: { show: true, color: '#9fc4d7', fontSize: 8 } }))]
  return {
    backgroundColor: 'transparent', tooltip: { trigger: 'item' },
    geo: { map: 'aigc-world', roam: false, silent: true, top: '8%', bottom: '12%', left: '5%', right: '5%', itemStyle: { areaColor: '#102f45', borderColor: '#2a607d', borderWidth: .6 }, emphasis: { disabled: true } },
    series: [{ type: 'graph', layout: 'circular', left: '17%', right: '17%', top: '18%', bottom: '18%', data: nodes, links: sources.map((_, index) => ({ source: `source-${index}`, target: 'platform', lineStyle: { color: sources[index].alerts ? '#ff5869' : '#31c6dc', opacity: .55, curveness: .15 } })), lineStyle: { width: 1 }, symbol: 'circle', animationDurationUpdate: 900 }],
  }
})
const radarOption = computed<EChartsCoreOption>(() => {
  const summary = data.value?.summary
  const models = data.value?.service_health
  const incidentHandled = summary?.alerts ? Math.min(100, Math.round((summary.blocked / summary.alerts) * 100)) : 100
  const latencyHealth = summary ? Math.max(0, Math.min(100, Math.round(100 - summary.p95_latency_ms / 50))) : 0
  return {
    backgroundColor: 'transparent', tooltip: {},
    radar: { radius: '65%', center: ['50%', '52%'], indicator: [{ name: '成功率', max: 100 }, { name: '响应健康', max: 100 }, { name: '风险处置', max: 100 }, { name: '审计完整', max: 100 }, { name: '引擎就绪', max: 100 }], axisName: { color: '#7fa2b6', fontSize: 9 }, splitArea: { areaStyle: { color: ['rgba(49,198,220,.02)', 'rgba(49,198,220,.06)'] } }, splitLine: { lineStyle: { color: '#24506b' } }, axisLine: { lineStyle: { color: '#24506b' } } },
    series: [{ type: 'radar', data: [{ value: [summary?.success_rate || 0, latencyHealth, incidentHandled, data.value?.service_health.audit_chain === 'healthy' ? 100 : 0, models ? Math.round(models.configured_models / models.total_models * 100) : 0], areaStyle: { color: 'rgba(49,198,220,.20)' }, lineStyle: { color: '#31c6dc', width: 2 }, itemStyle: { color: '#4ddeaa' } }] }],
  }
})

async function exitScreen() { if (document.fullscreenElement) await document.exitFullscreen().catch(() => undefined); router.push('/dashboard') }
function formatTime(value: string) { return new Date(value).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) }
function statusLabel(status: string) { return ({ enabled: '运行', configured: '就绪', standby: '待机', degraded: '异常', unconfigured: '未配置' } as Record<string, string>)[status] || status }
onMounted(() => { clockTimer = setInterval(() => { now.value = new Date() }, 1000) })
onBeforeUnmount(() => { if (clockTimer) clearInterval(clockTimer) })
</script>

<style scoped>
:global(body:has(.big-screen)){overflow:hidden}.big-screen{position:fixed;inset:0;z-index:500;display:flex;flex-direction:column;min-width:1024px;min-height:640px;padding:12px 16px 10px;color:#d9edf7;background:#071b2a;background-image:linear-gradient(rgba(62,135,171,.08) 1px,transparent 1px),linear-gradient(90deg,rgba(62,135,171,.08) 1px,transparent 1px);background-size:38px 38px}.screen-header{height:62px;display:grid;grid-template-columns:1fr auto 1fr;align-items:center;border-bottom:1px solid #214861;position:relative}.screen-header::after{content:'';position:absolute;left:32%;right:32%;bottom:-1px;height:2px;background:#31c6dc;box-shadow:0 0 14px #31c6dc}.brand-lockup{display:flex;align-items:center;gap:10px;color:#31c6dc}.brand-lockup div{display:flex;flex-direction:column}.brand-lockup strong{font-size:13px}.brand-lockup span{margin-top:3px;color:#688da3;font:8px ui-monospace,monospace}.screen-title{font-size:22px;font-weight:750;color:#e8f7ff}.screen-clock{display:grid;grid-template-columns:auto 34px;justify-content:end;align-items:center;column-gap:12px}.screen-clock strong{font:18px ui-monospace,monospace;color:#7de8f5}.screen-clock span{grid-column:1;color:#6f94aa;font-size:9px;text-align:right}.screen-clock button{grid-column:2;grid-row:1/3;width:34px;height:34px;display:grid;place-items:center;color:#8bb3c7;background:#0d2c40;border:1px solid #27536d;border-radius:5px;cursor:pointer}.screen-kpis{height:80px;display:grid;grid-template-columns:repeat(6,1fr);gap:10px;padding:10px 0}.screen-kpis>div{display:grid;grid-template-columns:1fr auto;align-content:center;padding:8px 12px;background:#0a2639;border:1px solid #1d4862;border-left:3px solid #31c6dc}.screen-kpis span{font-size:9px;color:#779cb0}.screen-kpis strong{grid-row:1/3;grid-column:2;font:25px ui-monospace,monospace;color:#dff8ff}.screen-kpis small{font:8px ui-monospace,monospace;color:#4e7489}.screen-kpis .risk{border-left-color:#ff5869}.screen-kpis .risk strong{color:#ff7a87}.screen-grid{flex:1;min-height:0;display:grid;grid-template-columns:25% 50% 25%;grid-template-rows:minmax(0,1fr) 150px;gap:10px}.screen-column{min-width:0;min-height:0;display:grid;grid-template-rows:1fr 1fr;gap:10px}.screen-panel{position:relative;min-width:0;min-height:0;background:rgba(8,31,47,.92);border:1px solid #1d4862;overflow:hidden}.screen-panel::before,.screen-panel::after{content:'';position:absolute;width:13px;height:13px;border-color:#31c6dc;z-index:2}.screen-panel::before{left:-1px;top:-1px;border-left:2px solid;border-top:2px solid}.screen-panel::after{right:-1px;bottom:-1px;border-right:2px solid;border-bottom:2px solid}.screen-panel :deep(.panel-title){height:38px;display:flex;align-items:center;padding:0 12px;border-bottom:1px solid rgba(43,94,122,.65)}.screen-panel :deep(.panel-title strong){font-size:11px;color:#d8eef7}.screen-panel :deep(.panel-title span){margin-left:auto;color:#49758c;font:8px ui-monospace,monospace}.screen-panel>.base-chart{height:calc(100% - 38px);min-height:0}.situation{grid-column:2;grid-row:1}.topology-note{position:absolute;left:12px;bottom:40px;color:#557f95;font-size:8px}.situation-foot{position:absolute;left:12px;right:12px;bottom:10px;display:flex;justify-content:center;gap:22px;color:#779cb0;font-size:8px}.situation-foot span{display:flex;align-items:center;gap:5px}.situation-foot i{width:6px;height:6px;border-radius:50%;background:#4ddeaa;box-shadow:0 0 8px #4ddeaa}.situation-foot i.cyan{background:#31c6dc}.situation-foot i.danger{background:#ff5869}.engine-grid{height:calc(100% - 38px);display:grid;grid-template-columns:1fr 1fr;padding:8px 12px;gap:5px 12px}.engine-grid>div{min-width:0;display:grid;grid-template-columns:8px 1fr auto;align-content:center;column-gap:7px;border-bottom:1px solid rgba(37,80,107,.5)}.engine-grid i{width:7px;height:7px;margin-top:3px;border-radius:50%;background:#597c90}.engine-grid i.enabled,.engine-grid i.configured{background:#4ddeaa;box-shadow:0 0 8px #4ddeaa}.engine-grid i.standby{background:#ffb454}.engine-grid span{font-size:9px}.engine-grid strong{font-size:8px;color:#75cadd}.engine-grid small{grid-column:2/4;margin-top:3px;color:#52778b;font-size:7px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.alerts{grid-column:1/4;grid-row:2}.ticker{height:calc(100% - 38px);display:grid;grid-template-columns:1fr 1fr;grid-auto-rows:26px;column-gap:24px;padding:7px 12px;overflow:hidden}.ticker>div{min-width:0;display:grid;grid-template-columns:58px 100px 1fr 110px;align-items:center;gap:8px;border-bottom:1px solid rgba(37,80,107,.45);font-size:8px}.ticker time{color:#557f95;font-family:ui-monospace,monospace}.ticker b{color:#ffb454}.ticker b.high,.ticker b.critical{color:#ff6a78}.ticker span{color:#95b7c8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ticker code{color:#52778b;text-align:right}.screen-empty{height:calc(100% - 38px);display:grid;place-items:center;color:#52778b;font-size:9px}.screen-footer{height:30px;display:flex;align-items:center;gap:22px;color:#496f84;font:8px ui-monospace,monospace}.screen-footer span:nth-child(2){flex:1;text-align:center}.screen-footer strong{color:#7ea2b4;font-weight:500}.screen-footer>i{width:6px;height:6px;border-radius:50%;background:#31c6dc}.screen-state{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;color:#7da3b7}.screen-state button{height:34px;padding:0 14px;color:#071b2a;background:#31c6dc;border:0;border-radius:5px;cursor:pointer}.spin{animation:rotate .9s linear infinite}@keyframes rotate{to{transform:rotate(360deg)}}@media(max-aspect-ratio:1.45){.screen-grid{grid-template-columns:28% 44% 28%}.screen-title{font-size:18px}}
.engine-grid i.degraded{background:#ff5869}
</style>
