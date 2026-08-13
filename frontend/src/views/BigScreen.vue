<template>
  <CockpitShell>
    <CockpitHeader title="AIGC 安全可视化驾驶舱" subtitle="AI SECURITY COMMAND CENTER" :clock="clock" :date="date" @exit="exitScreen" />
    <div v-if="authRequired" class="screen-state"><LockKeyhole :size="28" /><strong>审核员会话已失效</strong><button @click="openLogin">重新登录</button></div>
    <div v-else-if="!data" class="screen-state"><LoaderCircle :size="28" class="spin" /><strong>{{ error || '正在汇聚安全数据' }}</strong></div>
    <template v-else>
      <CockpitKpiRail>
        <CockpitMetric label="接口调用" :subtitle="overviewScopeLabel" :value="overviewSummary.request_count"><template #icon><ClipboardCheck /></template></CockpitMetric>
        <CockpitMetric label="审计日志" :subtitle="overviewScopeLabel" :value="overviewSummary.total_events" tone="cyan"><template #icon><ShieldAlert /></template></CockpitMetric>
        <CockpitMetric label="风险告警" :subtitle="`BLOCKED ${overviewSummary.blocked} · ${overviewScopeLabel}`" :value="overviewSummary.alerts" tone="red" :alert="data.summary.alerts > 0"><template #icon><Siren /></template></CockpitMetric>
        <CockpitMetric label="来源主体" :subtitle="overviewScopeLabel" :value="overviewSummary.unique_clients" tone="mint"><template #icon><Network /></template></CockpitMetric>
        <CockpitMetric label="P95 延迟" :subtitle="`MS · 健康 ${latencyHealthScore(overviewSummary.p95_latency_ms)}`" :value="overviewSummary.p95_latency_ms" tone="violet"><template #icon><Gauge /></template></CockpitMetric>
        <CockpitMetric label="检测报告" :subtitle="`${data.reports.total} TOTAL · 查看报告`" :value="data.reports.in_window" interactive action-label="进入审计与取证报告" @activate="openReports"><template #icon><FileCheck2 /></template></CockpitMetric>
      </CockpitKpiRail>
      <main class="cockpit-layout">
        <aside class="left-column">
          <CockpitPanel class="intro-panel" title="平台简介" code="PLATFORM PROFILE">
            <section class="platform-intro">
              <p class="intro-slogan">不是“反 AI”，而是让 AI 内容可验证、可解释、可追溯、可处置。</p>
              <div class="intro-overview"><span class="intro-emblem"><ShieldCheck :size="26" /></span><p>平台面向图片、人脸、文本与 Agent，识别真实性风险和内容安全风险，帮助审核员判断内容能否发布、是否需要复核，以及为什么触发策略。</p></div>
              <p class="intro-future">从输入采集开始，经过多模型判定、红线知识检索和策略融合，最终输出“放行 / 复核 / 阻断”，全程保留可审计证据。</p>
              <ul class="intro-features">
                <li><b>真实性鉴别</b><span>Deepfake、AI 生图与来源凭证</span></li>
                <li><b>内容安全</b><span>成人、暴力、违法与隐私风险</span></li>
                <li><b>模型护栏</b><span>输入输出、越狱与 Agent 操作</span></li>
                <li><b>审计闭环</b><span>解释证据、人工复核与 API 接入</span></li>
              </ul>
              <dl><div><dt>公网来源</dt><dd>{{ sourceBreakdown.public }}</dd></div><div><dt>内部 / 测试</dt><dd>{{ sourceBreakdown.internal }}</dd></div><div><dt>原图公开</dt><dd>否</dd></div></dl>
            </section>
          </CockpitPanel>
          <CockpitPanel class="trend" title="日志与告警趋势" :code="usingHistory ? '7D EVENT TREND' : '24H EVENT TREND'" tone="cyan" flush><BaseChart :option="trendOption" aria-label="日志与告警趋势图" dark /></CockpitPanel>
          <CockpitPanel class="ring" title="风险类别分布" :code="riskScopeLabel" tone="violet" flush><BaseChart :option="riskOption" aria-label="风险类别分布图" dark /></CockpitPanel>
        </aside>
        <CockpitPanel class="situation" title="多模态审核防御链" code="DEFENSE PIPELINE" focus flush><template #meta><span class="situation-badge"><i></i>实时运行</span></template><CockpitCore :configured-models="data.service_health.configured_models" :total-models="data.service_health.total_models" :audit-healthy="data.service_health.audit_chain === 'healthy'" :running="!loading" /><div class="situation-foot"><span><i></i>主系统在线</span><span><i class="cyan"></i>{{ data.service_health.configured_models }}/{{ data.service_health.total_models }} 引擎就绪</span><span><i :class="{danger:data.service_health.audit_chain !== 'healthy'}"></i>审计链{{ data.service_health.audit_chain === 'healthy' ? '完整' : '异常' }}</span></div></CockpitPanel>
        <aside class="right-column">
          <CockpitPanel class="alerts" :title="data.recent_alerts.length ? '实时风险事件' : '安全态势概览'" :code="data.recent_alerts.length ? 'LIVE ALERTS' : '7D OVERVIEW · IP REGIONS'" :tone="data.recent_alerts.length ? 'danger' : 'blue'" flush>
            <CockpitAlertFeed v-if="data.recent_alerts.length" :items="data.recent_alerts" />
            <CockpitSituationOverview v-else :summary="data.historical.summary" :regions="data.source_regions" />
          </CockpitPanel>
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
import { ClipboardCheck, FileCheck2, Gauge, LoaderCircle, LockKeyhole, Network, ShieldAlert, ShieldCheck, Siren } from 'lucide-vue-next'
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
import CockpitSituationOverview from '../components/dashboard/CockpitSituationOverview.vue'
import CockpitTrendChart from '../components/dashboard/CockpitTrendChart.vue'
import LoginDialog from '../components/auth/LoginDialog.vue'
import RiskSampleStrip, { type DemoRiskSample } from '../components/dashboard/RiskSampleStrip.vue'
import { useDashboard } from '../composables/useDashboard'
import { alpha, areaGradient, axisBase, categoryColor, token, tooltipBase } from '../lib/screenTheme'
import '../styles/screen-tokens.css'

const router = useRouter(); const { data, loading, error, authRequired } = useDashboard(); const now = ref(new Date()); const loginOpen = ref(false); const demoSamples = ref<DemoRiskSample[]>([]); let clockTimer: ReturnType<typeof setInterval> | null = null; let sampleController: AbortController | null = null
const clock = computed(() => now.value.toLocaleTimeString('zh-CN', { hour12: false })); const date = computed(() => now.value.toLocaleDateString('zh-CN', { year:'numeric', month:'2-digit', day:'2-digit', weekday:'short' }))
const sourceScope=(value?:string)=>{const s=(value||'').trim().toLowerCase(); if(!s||s==='internal'||s==='testclient'||s==='localhost') return 'internal'; const p=s.split('.').map(Number); if(p.length!==4||p.some(n=>!Number.isInteger(n)||n<0||n>255)) return 'internal'; return p[0]===10||p[0]===127||(p[0]===192&&p[1]===168)||(p[0]===172&&p[1]>=16&&p[1]<=31)?'internal':'public'}
const sourceBreakdown = computed(() => { const current=data.value?.top_sources||[]; const sources=current.length?current:(data.value?.historical.top_sources||[]); return sources.reduce((t,s) => { t[sourceScope(s.client_ip)] += 1; return t }, { public:0, internal:0 } as Record<'public'|'internal',number>) })
const categoryNames:Record<string,string>={jailbreak:'越狱攻击',prompt_injection:'提示词注入',prompt_injection_and_jailbreak:'提示词攻击',cyber_abuse:'网络攻击滥用',weapons_violence:'武器与暴力',self_harm:'自伤风险',sexual_content:'色情内容',adult_content:'成人内容',child_safety:'未成年人安全',personal_data:'隐私数据',sensitive_data:'敏感数据',illegal_activity:'违法活动',agent_security:'智能体安全',agent_tool_abuse:'工具调用滥用',weapon_display:'武器展示',violence:'暴力血腥',graphic_violence:'暴力血腥',political_sensitive:'政治敏感',policy_violation:'策略违规',marketing_violation:'营销违规',content_safety:'内容安全',unsafe:'不安全内容',misinformation:'虚假信息',critical:'严重风险',high:'高风险',warning:'中风险',unclassified:'未分类风险',other:'其他风险'}
function latencyHealthScore(ms:number){const healthy=5000,critical=60000;return ms<=healthy?100:ms>=critical?0:Math.round(100*(critical-ms)/(critical-healthy))}
const EXPECTED_SITUATION_SOURCES = 3
const usingHistory = computed(() => Boolean(data.value && data.value.summary.total_events === 0 && data.value.historical.summary.total_events > 0))
const overviewSummary = computed(() => usingHistory.value ? data.value!.historical.summary : data.value!.summary)
const overviewTimeline = computed(() => usingHistory.value ? data.value!.historical.timeline : data.value!.timeline)
const overviewScopeLabel = computed(() => usingHistory.value ? '7D OVERVIEW' : `${data.value?.window.hours || 24}H WINDOW`)
const riskScopeLabel = computed(() => {
  if (riskItems.value.length && (data.value?.risk_distribution || []).some(item => item.value > 0)) return '24 小时风险画像'
  if ((data.value?.historical.risk_distribution || []).some(item => item.value > 0)) return '7 天风险画像'
  return '精选样本画像'
})
const riskItems = computed(() => {
  const source = data.value?.risk_distribution || []
  const sourceTotal = source.reduce((sum, item) => sum + Math.max(0, Number(item.value) || 0), 0)
  if (source.length && sourceTotal > 0) return source
  const historical = data.value?.historical.risk_distribution || []
  if (historical.some(item => item.value > 0)) return historical
  const alerts = data.value?.recent_alerts || []
  const counts = alerts.reduce<Record<string, number>>((result, item) => {
    const key = item.risk_code || item.severity || 'unclassified'
    result[key] = (result[key] || 0) + 1
    return result
  }, {})
  if (!Object.keys(counts).length && data.value?.summary.alerts) return [{ name: 'unclassified', value: data.value.summary.alerts }]
  if (Object.keys(counts).length) return Object.entries(counts).map(([name, value]) => ({ name, value }))
  return Object.entries(demoSamples.value.reduce<Record<string,number>>((result,item)=>{const key=item.risk_category||'样本库';result[key]=(result[key]||0)+1;return result},{})).map(([name,value])=>({name,value}))
})
const localizedRiskItems = computed(() => {
  const grouped = new Map<string,{name:string;value:number;rawName:string}>()
  for (const item of riskItems.value) {
    const name = categoryLabel(item.name)
    const current = grouped.get(name)
    if (current) current.value += item.value
    else grouped.set(name,{name,value:item.value,rawName:item.name})
  }
  return [...grouped.values()].sort((a,b)=>b.value-a.value)
})
const trendOption=computed<EChartsCoreOption>(()=>{const accent=token('--sc-accent'),danger=token('--sc-critical'),timeline=overviewTimeline.value,alerts=timeline.map(i=>i.alerts),peak=Math.max(0,...alerts);return {backgroundColor:'transparent',tooltip:{trigger:'axis',confine:true,...tooltipBase()},legend:{data:['审计日志','风险告警'],right:8,top:4,itemWidth:12,itemHeight:3,textStyle:{color:token('--sc-ink-3'),fontSize:10}},grid:{left:8,right:10,top:28,bottom:4,containLabel:true},xAxis:{type:'category',boundaryGap:false,data:timeline.map(i=>new Date(i.start).toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit',hour12:false})),...axisBase()},yAxis:{type:'value',minInterval:1,...axisBase(),axisLine:{show:false},splitLine:{lineStyle:{color:token('--sc-line-soft'),type:'dashed'}}},series:[{name:'审计日志',type:'line',smooth:.32,showSymbol:false,lineStyle:{color:accent,width:2.2,shadowColor:alpha(accent,.7),shadowBlur:10},areaStyle:{color:areaGradient(accent,.3)},data:timeline.map(i=>i.events)},{name:'风险告警',type:'line',smooth:.32,showSymbol:false,lineStyle:{color:danger,width:2,shadowColor:alpha(danger,.65),shadowBlur:10},areaStyle:{color:areaGradient(danger,.16)},markPoint:peak?{symbolSize:34,data:[{type:'max'}],itemStyle:{color:alpha(danger,.9)},label:{color:'#fff',fontSize:9}}:undefined,data:alerts}]}})
const riskOption=computed<EChartsCoreOption>(()=>{const items=localizedRiskItems.value,total=items.reduce((s,i)=>s+i.value,0),centerLabel=riskScopeLabel.value==='精选样本画像'?'样本总量':'风险总量',panelBg=token('--screen-bg');return {backgroundColor:'transparent',tooltip:{trigger:'item',confine:true,...tooltipBase()},legend:{type:'scroll',orient:'vertical',right:4,top:'middle',height:'84%',itemGap:7,selectedMode:false,textStyle:{color:token('--sc-ink-2'),fontSize:10},formatter:(name:string)=>{const hit=items.find(i=>i.name===name);return `${name}  ${hit&&total?Math.round(hit.value/total*1000)/10:0}%`}},series:[{type:'pie',radius:['45%','68%'],center:['26%','52%'],label:{show:false},labelLine:{show:false},itemStyle:{borderColor:panelBg,borderWidth:2,borderRadius:3},emphasis:{scale:true,scaleSize:4},data:items.map((i,n)=>({name:i.name,value:i.value,itemStyle:{color:categoryColor(i.rawName,n),borderColor:panelBg,borderWidth:2}}))},{type:'pie',radius:0,center:['26%','52%'],silent:true,animation:false,tooltip:{show:false},data:[{value:1,itemStyle:{color:'transparent'},label:{show:true,position:'center',formatter:`{value|${total}}\n{label|${centerLabel}}`,rich:{value:{color:token('--sc-ink'),fontSize:20,fontWeight:700,fontFamily:token('--font-number'),lineHeight:25,align:'center'},label:{color:token('--sc-ink-3'),fontSize:9,lineHeight:14,align:'center'}}}}]}]}})
const radarOption=computed<EChartsCoreOption>(()=>{const summary=overviewSummary.value,health=data.value?.service_health,accent=token('--screen-core-blue'),fill=token('--screen-core-light');const engineReadiness=health?.total_models?Math.round(health.configured_models/health.total_models*100):0;const observed=summary.total_events>0;const availability=observed?summary.success_rate:(health?.api==='online'?engineReadiness:0);const latency=observed?latencyHealthScore(summary.p95_latency_ms):(health?.api==='online'?100:0);const situationCoverage=Math.round(Math.min(data.value?.data_sources.length||0,EXPECTED_SITUATION_SOURCES)/EXPECTED_SITUATION_SOURCES*100);return {backgroundColor:'transparent',tooltip:{show:false},radar:{radius:'52%',center:['50%','56%'],indicator:[{name:'检测可用性',max:100},{name:'响应时效',max:100},{name:'态势感知',max:100},{name:'审计可信度',max:100},{name:'引擎就绪性',max:100}],axisName:{color:token('--sc-ink-2'),fontSize:10},splitArea:{areaStyle:{color:[alpha(accent,.015),alpha(accent,.055)]}},splitLine:{lineStyle:{color:token('--sc-line-soft')}},axisLine:{lineStyle:{color:token('--sc-line-2')}}},series:[{type:'radar',symbolSize:5,data:[{value:[availability,latency,situationCoverage,health?.audit_chain==='healthy'?100:0,engineReadiness],areaStyle:{color:alpha(fill,.16)},lineStyle:{color:accent,width:2,shadowColor:alpha(accent,.7),shadowBlur:10},itemStyle:{color:token('--sc-ink'),borderColor:accent,borderWidth:2}}]}]}})
function categoryLabel(value:string){const key=String(value||'').trim();if(categoryNames[key])return categoryNames[key];if(/[\u4e00-\u9fff]/.test(key))return key;if(/^GR-BLOCK/i.test(key)||/^AGENT-BLOCK/i.test(key))return '安全策略阻断';if(/^GR-REVIEW/i.test(key)||/REVIEW|APPROVAL/i.test(key))return '待人工复核';return '未分类风险'}
async function loadDemoSamples(){sampleController?.abort();sampleController=new AbortController();try{const r=await fetch('/demo-samples/catalog.json',{signal:sampleController.signal,cache:'no-store'});if(r.ok){const body=await r.json();demoSamples.value=Array.isArray(body.samples)?body.samples:[]}}catch(e){if((e as Error).name!=='AbortError')demoSamples.value=[]}}
function openLogin(){loginOpen.value=true} async function leaveScreen(path:string){if(document.fullscreenElement)await document.exitFullscreen().catch(()=>undefined);router.push(path)} async function openReports(){await leaveScreen('/report')} async function exitScreen(){await leaveScreen('/dashboard')}
onMounted(()=>{clockTimer=setInterval(()=>{now.value=new Date()},1000);loadDemoSamples()});onBeforeUnmount(()=>{if(clockTimer)clearInterval(clockTimer);sampleController?.abort()})
</script>

<style scoped>
.cockpit-layout{display:grid;grid-template:"left core right" minmax(0,1fr) "samples samples samples" auto / minmax(260px,27fr) minmax(560px,46fr) minmax(260px,27fr);gap:var(--screen-gap);flex:1;min-height:0}.left-column,.right-column{display:flex;min-width:0;min-height:0;flex-direction:column;gap:var(--screen-gap)}.left-column{grid-area:left}.right-column{grid-area:right}.situation{grid-area:core}.samples-panel{grid-area:samples;min-height:180px}.left-column>.intro-panel{flex:.84}.left-column>.trend{flex:1}.left-column>.ring{flex:.92}.right-column>.alerts{flex:1.2}.right-column>.radar{flex:.9}.right-column>.engines{flex:.92}.platform-intro{display:flex;min-height:0;flex:1;flex-direction:column;overflow:hidden}.platform-intro p{margin:0;color:var(--sc-ink-2);font-size:var(--sc-fs-aux);line-height:1.65}.platform-intro .intro-future{margin-top:8px;padding-left:8px;color:var(--sc-ink-3);border-left:2px solid rgba(60,232,170,.55)}.capability-tags{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0}.capability-tags span{padding:3px 8px;color:#a8f0ff;background:var(--sc-accent-soft);border:1px solid rgba(112,224,255,.25);border-radius:4px;font-size:var(--sc-fs-code)}.platform-intro dl{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin:auto 0 0}.platform-intro dl>div{padding:7px 8px;background:rgba(10,36,58,.38);border-bottom:1px solid var(--screen-line-soft)}.platform-intro dt{color:var(--sc-ink-4);font-size:var(--sc-fs-code)}.platform-intro dd{margin:4px 0 0;color:var(--sc-ink);font:600 var(--sc-fs-body) var(--font-number)}.situation-badge{display:inline-flex;align-items:center;gap:5px;color:var(--sc-mint);font:var(--sc-fs-code) var(--font-code)}.situation-badge i,.situation-foot i{width:6px;height:6px;border-radius:50%;background:currentColor;box-shadow:0 0 8px currentColor}.situation-foot{position:absolute;left:14px;right:14px;bottom:8px;display:flex;justify-content:center;gap:24px;color:var(--sc-ink-3);font-size:var(--sc-fs-code)}.situation-foot span{display:flex;align-items:center;gap:6px}.situation-foot .cyan{color:var(--sc-cyan)}.situation-foot .danger{color:var(--sc-danger)}.screen-state{display:grid;flex:1;place-items:center;align-content:center;gap:12px;color:var(--screen-text-muted)}.screen-state strong{color:var(--screen-text);font-size:var(--fs-screen-title)}.screen-state button{padding:8px 16px;color:#03101f;background:var(--screen-blue);border:0;border-radius:var(--screen-radius-sm);font-weight:600;cursor:pointer}.spin{animation:spin .9s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}@media(max-width:1199px){.cockpit-layout{grid-template-columns:minmax(0,25fr) minmax(0,50fr) minmax(0,25fr);grid-template-rows:minmax(0,1fr) 184px}.samples-panel{min-height:184px}.situation-foot{display:none}.left-column,.right-column{gap:9px}}@media(max-height:800px){.platform-intro .intro-future{display:none}.capability-tags{margin:5px 0}}@media(prefers-reduced-motion:reduce){.spin{animation:none}}
.cockpit-layout{grid-template-rows:minmax(0,1fr) 248px}
.cockpit-layout{grid-template-columns:minmax(260px,27fr) minmax(560px,46fr) minmax(260px,27fr)}
.samples-panel{min-height:0}
.situation-foot{display:flex}.left-column,.right-column{gap:var(--screen-gap)}.platform-intro .intro-future{display:block}.capability-tags{margin:10px 0}
.left-column>.intro-panel{flex:1.08}.left-column>.trend{flex:1.02}.left-column>.ring{flex:.72}.right-column>.alerts{flex:1.05}.right-column>.radar{flex:1.15}.right-column>.engines{flex:.82}
.situation :deep(.panel-body){padding-bottom:30px}.situation-foot{bottom:5px;z-index:9;min-height:21px;align-items:center;background:linear-gradient(90deg,transparent,rgba(3,24,48,.86) 18%,rgba(3,24,48,.86) 82%,transparent);font-size:11px}
.intro-slogan{padding:7px 9px;color:var(--sc-ink)!important;background:linear-gradient(90deg,rgba(22,140,255,.15),transparent);border-left:2px solid var(--sc-accent);font-weight:650;line-height:1.45!important;text-shadow:0 0 10px rgba(42,151,255,.18)}.intro-overview{display:flex;align-items:center;gap:10px;margin-top:8px}.intro-overview p{line-height:1.55}.intro-emblem{position:relative;flex:0 0 46px;width:46px;height:52px;display:grid;place-items:center;color:#dff8ff;background:linear-gradient(145deg,rgba(25,142,222,.72),rgba(3,39,83,.92));clip-path:polygon(50% 0,93% 24%,93% 76%,50% 100%,7% 76%,7% 24%);filter:drop-shadow(0 0 9px rgba(22,140,255,.34))}.intro-emblem::before{content:'';position:absolute;inset:5px;clip-path:inherit;border:1px solid rgba(205,245,255,.42)}.intro-emblem :deep(svg){position:relative;z-index:1;stroke-width:1.8}.intro-features{display:grid;grid-template-columns:1fr 1fr;gap:5px 10px;margin:9px 0 7px;padding:0;list-style:none}.intro-features li{position:relative;min-width:0;padding-left:10px;line-height:1.35}.intro-features li::before{content:'';position:absolute;left:0;top:6px;width:4px;height:4px;border-radius:50%;background:var(--sc-cyan);box-shadow:0 0 7px var(--sc-cyan)}.intro-features b{display:block;color:var(--sc-cyan);font-size:11px}.intro-features span{display:block;overflow:hidden;color:var(--sc-ink-3);font-size:10px;text-overflow:ellipsis;white-space:nowrap}.platform-intro dl{margin-top:auto}
</style>
