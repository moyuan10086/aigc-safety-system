<template>
  <CockpitShell>
    <CockpitHeader title="AIGC 安全可视化驾驶舱" subtitle="AI SECURITY COMMAND CENTER" :clock="clock" :date="date" @exit="exitScreen" />
    <div v-if="authRequired" class="screen-state"><LockKeyhole :size="28" /><strong>审核员会话已失效</strong><button @click="openLogin">重新登录</button></div>
    <div v-else-if="!data" class="screen-state"><LoaderCircle :size="28" class="spin" /><strong>{{ error || '正在汇聚安全数据' }}</strong></div>
    <template v-else>
      <CockpitKpiRail>
        <CockpitMetric label="审核任务" :subtitle="`${data.window.hours}H WINDOW`" :value="data.summary.business_reviews"><template #icon><ClipboardCheck /></template></CockpitMetric>
        <CockpitMetric label="安全事件" subtitle="REAL INCIDENTS" :value="data.summary.total_events" tone="cyan"><template #icon><ShieldAlert /></template></CockpitMetric>
        <CockpitMetric label="风险告警" :subtitle="`BLOCKED ${data.summary.blocked}`" :value="data.summary.alerts" tone="red" :alert="data.summary.alerts > 0"><template #icon><Siren /></template></CockpitMetric>
        <CockpitMetric label="来源主体" subtitle="PUBLIC + INTERNAL" :value="data.summary.unique_clients" tone="mint"><template #icon><Network /></template></CockpitMetric>
        <CockpitMetric label="P95 延迟" :subtitle="`MS · 健康 ${latencyHealthScore(data.summary.p95_latency_ms)}`" :value="data.summary.p95_latency_ms" tone="violet"><template #icon><Gauge /></template></CockpitMetric>
        <CockpitMetric label="检测报告" :subtitle="`${data.reports.total} TOTAL`" :value="data.reports.in_window"><template #icon><FileCheck2 /></template></CockpitMetric>
      </CockpitKpiRail>
      <main class="cockpit-layout">
        <aside class="left-column">
          <CockpitPanel class="intro-panel" title="平台简介" code="PLATFORM PROFILE"><div class="platform-intro"><p>平台不以“反 AI”为目标，而是把真实性、内容安全、来源凭证与人工复核编排为同一条审计链，识别伪造、风险与缺乏可追溯依据的自动化内容。</p><p class="intro-future">红线知识库覆盖敏感内容、隐私、违法诱导和提示注入；可扩展搜索支持的事实核验，将待验证主张送入审计队列。</p><div class="capability-tags"><span>真实性审计</span><span>内容安全</span><span>大模型护栏</span><span>C2PA 溯源</span></div><dl><div><dt>公网来源</dt><dd>{{ sourceBreakdown.public }}</dd></div><div><dt>内部 / 测试</dt><dd>{{ sourceBreakdown.internal }}</dd></div><div><dt>原图公开</dt><dd>否</dd></div></dl></div></CockpitPanel>
          <CockpitPanel class="trend" title="审核与告警趋势" code="EVENT TREND" tone="cyan" flush><BaseChart :option="trendOption" aria-label="审核与告警趋势图" dark /></CockpitPanel>
          <CockpitPanel class="ring" title="风险类别分布" code="RISK PROFILE" tone="violet" flush><BaseChart :option="riskOption" aria-label="风险类别分布图" dark /></CockpitPanel>
        </aside>
        <CockpitPanel class="situation" title="多模态审核防御链" code="DEFENSE PIPELINE" focus flush><template #meta><span class="situation-badge"><i></i>实时运行</span></template><CockpitCore :configured-models="data.service_health.configured_models" :total-models="data.service_health.total_models" :audit-healthy="data.service_health.audit_chain === 'healthy'" :running="!loading" /><div class="situation-foot"><span><i></i>主系统在线</span><span><i class="cyan"></i>{{ data.service_health.configured_models }}/{{ data.service_health.total_models }} 引擎就绪</span><span><i :class="{danger:data.service_health.audit_chain !== 'healthy'}"></i>审计链{{ data.service_health.audit_chain === 'healthy' ? '完整' : '异常' }}</span></div></CockpitPanel>
        <aside class="right-column">
          <CockpitPanel class="alerts" title="实时风险事件" code="LIVE ALERTS" :tone="data.recent_alerts.length ? 'danger' : 'blue'" flush><CockpitAlertFeed :items="data.recent_alerts" /></CockpitPanel>
          <CockpitPanel class="radar" title="防护能力态势" code="CAPABILITY POSTURE" tone="cyan" flush><BaseChart :option="radarOption" aria-label="防护能力雷达图" dark suppress-tooltip /></CockpitPanel>
          <CockpitPanel class="engines" title="模型与引擎" code="ENGINE STATUS" flush><CockpitEngineList :models="data.models" /></CockpitPanel>
        </aside>
        <CockpitPanel class="samples-panel" title="典型风险样本实测" code="CURATED BENCHMARK · SANITIZED" flush><RiskSampleStrip :samples="demoSamples" /></CockpitPanel>
      </main>
      <CockpitFooter :start="data.window.start" :end="data.window.end" :loading="loading" />
    </template>
    <LoginDialog :open="loginOpen" @close="loginOpen = false" />
  </CockpitShell>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { EChartsCoreOption } from 'echarts/core'
import { ClipboardCheck, FileCheck2, Gauge, LoaderCircle, LockKeyhole, Network, ShieldAlert, Siren } from 'lucide-vue-next'
import BaseChart from '../components/dashboard/BaseChart.vue'
import CockpitAlertFeed from '../components/dashboard/CockpitAlertFeed.vue'
import CockpitCapabilityChart from '../components/dashboard/CockpitCapabilityChart.vue'
import CockpitCore from '../components/dashboard/CockpitCore.vue'
import CockpitEngineList from '../components/dashboard/CockpitEngineList.vue'
import CockpitFooter from '../components/dashboard/CockpitFooter.vue'
import CockpitHeader from '../components/dashboard/CockpitHeader.vue'
import CockpitKpiRail from '../components/dashboard/CockpitKpiRail.vue'
import CockpitMetric from '../components/dashboard/CockpitMetric.vue'
import CockpitPanel from '../components/dashboard/CockpitPanel.vue'
import CockpitRiskChart from '../components/dashboard/CockpitRiskChart.vue'
import CockpitShell from '../components/dashboard/CockpitShell.vue'
import CockpitTrendChart from '../components/dashboard/CockpitTrendChart.vue'
import LoginDialog from '../components/auth/LoginDialog.vue'
import RiskSampleStrip, { type DemoRiskSample } from '../components/dashboard/RiskSampleStrip.vue'
import { useDashboard } from '../composables/useDashboard'
import { alpha, areaGradient, axisBase, categoryColor, token, tooltipBase } from '../lib/screenTheme'
import '../styles/screen-tokens.css'

const router = useRouter(); const { data, loading, error, authRequired } = useDashboard(); const now = ref(new Date()); const loginOpen = ref(false); const demoSamples = ref<DemoRiskSample[]>([]); let clockTimer: ReturnType<typeof setInterval> | null = null; let sampleController: AbortController | null = null
const clock = computed(() => now.value.toLocaleTimeString('zh-CN', { hour12: false })); const date = computed(() => now.value.toLocaleDateString('zh-CN', { year:'numeric', month:'2-digit', day:'2-digit', weekday:'short' }))
const sourceScope=(value?:string)=>{const s=(value||'').trim().toLowerCase(); if(!s||s==='internal'||s==='testclient'||s==='localhost') return 'internal'; const p=s.split('.').map(Number); if(p.length!==4||p.some(n=>!Number.isInteger(n)||n<0||n>255)) return 'internal'; return p[0]===10||p[0]===127||(p[0]===192&&p[1]===168)||(p[0]===172&&p[1]>=16&&p[1]<=31)?'internal':'public'}
const sourceBreakdown = computed(() => (data.value?.top_sources || []).reduce((t,s) => { t[sourceScope(s.client_ip)] += 1; return t }, { public:0, internal:0 } as Record<'public'|'internal',number>))
const categoryNames:Record<string,string>={jailbreak:'越狱攻击',prompt_injection:'提示词注入',cyber_abuse:'网络攻击滥用',weapons_violence:'武器暴力',self_harm:'自伤风险',sexual_content:'色情内容',child_safety:'未成年人安全',personal_data:'隐私数据',illegal_activity:'违法活动',unsafe:'不安全内容',misinformation:'虚假信息'}
function latencyHealthScore(ms:number){const healthy=5000,critical=60000;return ms<=healthy?100:ms>=critical?0:Math.round(100*(critical-ms)/(critical-healthy))}
const trendOption=computed<EChartsCoreOption>(()=>{const accent=token('--sc-accent'),danger=token('--sc-critical'),timeline=data.value?.timeline||[],alerts=timeline.map(i=>i.alerts),peak=Math.max(0,...alerts);return {backgroundColor:'transparent',tooltip:{trigger:'axis',confine:true,...tooltipBase()},legend:{data:['审核任务','风险告警'],right:8,top:4,itemWidth:12,itemHeight:3,textStyle:{color:token('--sc-ink-3'),fontSize:10}},grid:{left:8,right:10,top:28,bottom:4,containLabel:true},xAxis:{type:'category',boundaryGap:false,data:timeline.map(i=>new Date(i.start).toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit',hour12:false})),...axisBase()},yAxis:{type:'value',minInterval:1,...axisBase(),axisLine:{show:false},splitLine:{lineStyle:{color:token('--sc-line-soft'),type:'dashed'}}},series:[{name:'审核任务',type:'line',smooth:.32,showSymbol:false,lineStyle:{color:accent,width:2.2,shadowColor:alpha(accent,.7),shadowBlur:10},areaStyle:{color:areaGradient(accent,.3)},data:timeline.map(i=>i.events)},{name:'风险告警',type:'line',smooth:.32,showSymbol:false,lineStyle:{color:danger,width:2,shadowColor:alpha(danger,.65),shadowBlur:10},areaStyle:{color:areaGradient(danger,.16)},markPoint:peak?{symbolSize:34,data:[{type:'max'}],itemStyle:{color:alpha(danger,.9)},label:{color:'#fff',fontSize:9}}:undefined,data:alerts}]}})
const riskOption=computed<EChartsCoreOption>(()=>{const items=data.value?.risk_distribution||[],total=items.reduce((s,i)=>s+i.value,0);return {backgroundColor:'transparent',tooltip:{trigger:'item',confine:true,...tooltipBase()},legend:{type:'scroll',orient:'vertical',right:4,top:'middle',height:'84%',itemGap:7,selectedMode:false,textStyle:{color:token('--sc-ink-2'),fontSize:10},formatter:(name:string)=>{const hit=items.find(i=>i.name===name);return `${categoryNames[name]||name}  ${hit&&total?Math.round(hit.value/total*1000)/10:0}%`}},series:[{type:'pie',radius:['45%','68%'],center:['26%','52%'],label:{show:false},labelLine:{show:false},itemStyle:{borderColor:'#03101f',borderWidth:2,borderRadius:3},emphasis:{scale:true,scaleSize:4},data:items.length?items.map((i,n)=>({...i,itemStyle:{color:categoryColor(i.name,n),borderColor:'#03101f',borderWidth:2}})):[{name:'暂无风险事件',value:1,itemStyle:{color:'#244d68'}}]}]}})
const radarOption=computed<EChartsCoreOption>(()=>{const summary=data.value?.summary,health=data.value?.service_health,accent=token('--sc-accent'),cyan=token('--sc-cyan');const handled=summary?.alerts?Math.min(100,Math.round(summary.blocked/summary.alerts*100)):100;const latency=summary?latencyHealthScore(summary.p95_latency_ms):0;return {backgroundColor:'transparent',tooltip:{show:false},radar:{radius:'64%',center:['50%','54%'],indicator:[{name:'成功率',max:100},{name:'响应速度',max:100},{name:'风险处置',max:100},{name:'审计完整性',max:100},{name:'引擎就绪性',max:100}],axisName:{color:token('--sc-ink-2'),fontSize:10},splitArea:{areaStyle:{color:[alpha(accent,.02),alpha(accent,.06)]}},splitLine:{lineStyle:{color:token('--sc-line-soft')}},axisLine:{lineStyle:{color:token('--sc-line-2')}}},series:[{type:'radar',symbolSize:5,data:[{value:[summary?.success_rate||0,latency,handled,health?.audit_chain==='healthy'?100:0,health?Math.round(health.configured_models/health.total_models*100):0],areaStyle:{color:alpha(cyan,.16)},lineStyle:{color:accent,width:2,shadowColor:alpha(accent,.7),shadowBlur:10},itemStyle:{color:'#eafcff',borderColor:accent,borderWidth:2}}]}]}})
async function loadDemoSamples(){sampleController?.abort();sampleController=new AbortController();try{const r=await fetch('/demo-samples/catalog.json',{signal:sampleController.signal,cache:'no-store'});if(r.ok){const body=await r.json();demoSamples.value=Array.isArray(body.samples)?body.samples:[]}}catch(e){if((e as Error).name!=='AbortError')demoSamples.value=[]}}
function openLogin(){loginOpen.value=true} async function exitScreen(){if(document.fullscreenElement)await document.exitFullscreen().catch(()=>undefined);router.push('/dashboard')}
onMounted(()=>{clockTimer=setInterval(()=>{now.value=new Date()},1000);loadDemoSamples()});onBeforeUnmount(()=>{if(clockTimer)clearInterval(clockTimer);sampleController?.abort()})
</script>

<style scoped>
.cockpit-layout{display:grid;grid-template:"left core right" minmax(0,1fr) "samples samples samples" auto / minmax(260px,27fr) minmax(560px,46fr) minmax(260px,27fr);gap:var(--screen-gap);flex:1;min-height:0}.left-column,.right-column{display:flex;min-width:0;min-height:0;flex-direction:column;gap:var(--screen-gap)}.left-column{grid-area:left}.right-column{grid-area:right}.situation{grid-area:core}.samples-panel{grid-area:samples;min-height:180px}.left-column>.intro-panel{flex:.84}.left-column>.trend{flex:1}.left-column>.ring{flex:.92}.right-column>.alerts{flex:1.2}.right-column>.radar{flex:.9}.right-column>.engines{flex:.92}.platform-intro{display:flex;min-height:0;flex:1;flex-direction:column;overflow:hidden}.platform-intro p{margin:0;color:var(--sc-ink-2);font-size:var(--sc-fs-aux);line-height:1.65}.platform-intro .intro-future{margin-top:8px;padding-left:8px;color:var(--sc-ink-3);border-left:2px solid rgba(60,232,170,.55)}.capability-tags{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0}.capability-tags span{padding:3px 8px;color:#a8f0ff;background:var(--sc-accent-soft);border:1px solid rgba(112,224,255,.25);border-radius:4px;font-size:var(--sc-fs-code)}.platform-intro dl{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin:auto 0 0}.platform-intro dl>div{padding:7px 8px;background:rgba(10,36,58,.38);border-bottom:1px solid var(--screen-line-soft)}.platform-intro dt{color:var(--sc-ink-4);font-size:var(--sc-fs-code)}.platform-intro dd{margin:4px 0 0;color:var(--sc-ink);font:600 var(--sc-fs-body) var(--font-number)}.situation-badge{display:inline-flex;align-items:center;gap:5px;color:var(--sc-mint);font:var(--sc-fs-code) var(--font-code)}.situation-badge i,.situation-foot i{width:6px;height:6px;border-radius:50%;background:currentColor;box-shadow:0 0 8px currentColor}.situation-foot{position:absolute;left:14px;right:14px;bottom:8px;display:flex;justify-content:center;gap:24px;color:var(--sc-ink-3);font-size:var(--sc-fs-code)}.situation-foot span{display:flex;align-items:center;gap:6px}.situation-foot .cyan{color:var(--sc-cyan)}.situation-foot .danger{color:var(--sc-danger)}.screen-state{display:grid;flex:1;place-items:center;align-content:center;gap:12px;color:var(--screen-text-muted)}.screen-state strong{color:var(--screen-text);font-size:var(--fs-screen-title)}.screen-state button{padding:8px 16px;color:#03101f;background:var(--screen-blue);border:0;border-radius:var(--screen-radius-sm);font-weight:600;cursor:pointer}.spin{animation:spin .9s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}@media(max-width:1199px){.cockpit-layout{grid-template-columns:minmax(0,25fr) minmax(0,50fr) minmax(0,25fr);grid-template-rows:minmax(0,1fr) 184px}.samples-panel{min-height:184px}.situation-foot{display:none}.left-column,.right-column{gap:9px}}@media(max-height:800px){.platform-intro .intro-future{display:none}.capability-tags{margin:5px 0}}@media(prefers-reduced-motion:reduce){.spin{animation:none}}
.cockpit-layout{grid-template-rows:minmax(0,1fr) clamp(190px,23vh,248px)}
.samples-panel{min-height:0}
@media(max-width:1199px){.cockpit-layout{grid-template-rows:minmax(0,1fr) 184px}.samples-panel{min-height:0}}
</style>
