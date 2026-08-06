<template>
  <div ref="stageHost" class="pipeline-stage" :class="{ 'is-alert': alert }">
    <!-- 能量层：轨道、雷达、数据流粒子（纯装饰，不承载业务数值） -->
    <AiCoreCanvas class="core-energy" :intensity="intensity" :alert="alert" />

    <!-- 菱形技术网格，给中枢一个"空间基座" -->
    <div class="stage-grid" aria-hidden="true"></div>
    <div class="stage-cross" aria-hidden="true"></div>

    <!-- 核心球体：DOM 承载文案，保证换屏不模糊 -->
    <div class="core-shell">
      <div class="core-orb">
        <span class="orb-scan" aria-hidden="true"></span>
        <span class="orb-ring" aria-hidden="true"></span>
        <span class="orb-emblem"><ShieldCheck :size="38" /></span>
        <strong>安全审核中枢</strong>
        <span class="orb-code">POLICY ORCHESTRATOR</span>
        <b :class="{ degraded: configured < total }">
          <i aria-hidden="true"></i>{{ configured }}/{{ total }} 引擎在线
        </b>
      </div>
    </div>

    <!-- 四张能力卡：数据通道的外端 -->
    <div
      v-for="item in capabilities"
      :key="item.code"
      class="capability"
      :class="item.position"
    >
      <span class="cap-icon"><component :is="item.icon" :size="20" /></span>
      <div class="cap-copy">
        <strong>{{ item.label }}</strong>
        <span>{{ item.code }}</span>
      </div>
      <i class="cap-node" aria-hidden="true"></i>
    </div>

    <!-- 处置链路 -->
    <div class="decision-flow">
      <span>输入采集</span><i aria-hidden="true"></i>
      <span>多模态判定</span><i aria-hidden="true"></i>
      <span>策略融合</span><i aria-hidden="true"></i>
      <span class="terminal">放行 / 复核 / 阻断</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { BadgeCheck, BrainCircuit, ScanFace, ScanSearch, ShieldCheck, UserCheck } from 'lucide-vue-next'
import AiCoreCanvas from './AiCoreCanvas.vue'
import { orbDiameter } from '../../lib/coreGeometry'

const props = withDefaults(defineProps<{
  configured: number
  total: number
  /** 告警态：能量层与核心边缘转为风险色 */
  alert?: boolean
}>(), { alert: false })

// 数据流强度映射真实引擎就绪率，不是写死的观感参数
const intensity = computed(() => {
  if (!props.total) return 0.35
  return 0.35 + (props.configured / props.total) * 0.6
})

const capabilities = [
  { label: 'Deepfake 检测', code: 'DEEPFAKE / MLLM', icon: ScanFace, position: 'top-left' },
  { label: 'MLLM 理解分析', code: 'POLICY / LLM', icon: BrainCircuit, position: 'top-right' },
  { label: '实时防护', code: 'AUDIT / GUARDRAIL', icon: ShieldCheck, position: 'mid-left' },
  { label: 'RAG 内容审核', code: 'RAG / KNOWLEDGE', icon: ScanSearch, position: 'mid-right' },
  { label: '风险处置', code: 'REVIEW / ESCALATION', icon: UserCheck, position: 'bottom-left' },
  { label: '样本与取证', code: 'C2PA / HASH', icon: BadgeCheck, position: 'bottom-right' },
]

// 球体尺寸跟随 Canvas 的同一套几何：此前 CSS 写 17vw，与轨道半径无关，
// 导致轨道节点落在球体背后。改为从 coreGeometry 推导后两层始终同源。
const stageHost = ref<HTMLElement | null>(null)
let observer: ResizeObserver | null = null

function syncOrbSize() {
  const host = stageHost.value
  if (!host) return
  // The cockpit scene is transformed by its parent. Layout dimensions remain
  // in the 1920x1080 design coordinate system, unlike getBoundingClientRect().
  const width = host.clientWidth
  const height = host.clientHeight
  if (!width || !height) return
  host.style.setProperty('--core', `${Math.round(orbDiameter(width, height))}px`)
}

onMounted(() => {
  syncOrbSize()
  if (stageHost.value) {
    observer = new ResizeObserver(syncOrbSize)
    observer.observe(stageHost.value)
  }
})
onBeforeUnmount(() => observer?.disconnect())
</script>

<style scoped>
.pipeline-stage{
  /* --cy 必须与 AiCoreCanvas 的 CY_RATIO 一致，两层共享同一个圆心 */
  --cx:50%;
  --cy:46%;
  position:relative;
  flex:1;min-height:0;
  overflow:hidden;
  /* 中央比两侧亮一档：视觉重心由背景本身建立，而非只靠描边 */
  background:
    radial-gradient(ellipse 58% 48% at 50% 46%,var(--sc-nebula),transparent 72%),
    radial-gradient(ellipse 42% 36% at 22% 78%,var(--sc-nebula-2),transparent 70%),
    radial-gradient(ellipse 40% 34% at 82% 24%,var(--sc-nebula-3),transparent 70%);
}
.core-energy{z-index:1}

/* 菱形网格基座 */
.stage-grid{
  position:absolute;inset:7% 12% 15%;z-index:1;pointer-events:none;
  border:1px solid var(--sc-line-soft);
  background:
    repeating-linear-gradient(0deg,transparent 0 27px,var(--sc-grid-major) 28px),
    repeating-linear-gradient(90deg,transparent 0 27px,var(--sc-grid-major) 28px);
  clip-path:polygon(50% 0,100% 50%,50% 100%,0 50%);
  opacity:.7;
}
/* 十字准线，取景框语义 */
.stage-cross{position:absolute;inset:0;z-index:1;pointer-events:none}
.stage-cross::before,.stage-cross::after{
  content:'';position:absolute;left:var(--cx);top:var(--cy);
  transform:translate(-50%,-50%);
}
.stage-cross::before{
  width:74%;height:1px;
  background:linear-gradient(90deg,transparent,var(--sc-line),transparent);
}
.stage-cross::after{
  width:1px;height:66%;
  background:linear-gradient(180deg,transparent,var(--sc-line),transparent);
}

/* ---------- 核心球体 ---------- */
.core-shell{
  position:absolute;left:var(--cx);top:var(--cy);z-index:4;
  width:var(--core);aspect-ratio:1;
  transform:translate(-50%,-50%);
  pointer-events:none;
}
.core-orb{
  position:absolute;inset:0;
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  text-align:center;
  border-radius:50%;
  border:2px solid var(--sc-line-hi);
  /* 左上高光 + 中心亮到边缘暗的球面渐变 = 体积感 */
  background:
    radial-gradient(circle at 34% 26%,rgba(150,238,255,.34),transparent 54%),
    radial-gradient(circle at 50% 50%,#12648f 0%,#0a3c5c 44%,#062440 72%,#03172a 100%);
  box-shadow:
    0 0 0 7px rgba(42,201,255,.07),
    var(--sc-glow-3),
    inset 0 0 46px rgba(140,240,255,.20);
}
.pipeline-stage.is-alert .core-orb{
  border-color:rgba(255,122,145,.7);
  box-shadow:0 0 0 7px rgba(255,67,99,.08),0 0 26px rgba(255,120,145,.5),0 0 70px rgba(255,67,99,.3),inset 0 0 46px rgba(255,150,170,.18);
}
/* 内层虚线环缓慢自转 */
.orb-ring{
  position:absolute;inset:12px;border-radius:50%;
  border:1px dashed rgba(170,242,255,.40);
  animation:orb-spin 19s linear infinite;
}
.orb-ring::after{
  content:'';position:absolute;inset:9px;border-radius:50%;
  border:1px solid rgba(42,201,255,.22);
}
/* 上下往复的扫描亮带 */
.orb-scan{
  position:absolute;inset:12px;border-radius:50%;overflow:hidden;
  background:linear-gradient(180deg,transparent 45%,rgba(180,248,255,.30) 50%,transparent 55%);
  animation:orb-scan 3.8s ease-in-out infinite;
}
.orb-emblem{
  position:relative;width:56px;height:56px;
  display:grid;place-items:center;
  border-radius:50%;
  background:radial-gradient(circle,rgba(110,226,255,.26),transparent 70%);
  color:#e6fbff;
}
.orb-emblem::before,.orb-emblem::after{
  content:'';position:absolute;inset:-6px;border-radius:50%;
  border-top:1px solid rgba(180,246,255,.82);
  border-bottom:1px solid rgba(42,180,240,.32);
  transform:rotate(-24deg);
}
.orb-emblem::after{
  inset:-12px;
  border-top-color:rgba(42,201,255,.44);
  border-bottom-color:transparent;
  transform:rotate(140deg);
}
.orb-emblem :deep(svg){
  position:relative;z-index:1;stroke-width:1.8;
  filter:drop-shadow(0 0 11px rgba(140,240,255,.9));
}
/* 中枢标题是全屏第二重的文字（仅次于主标题） */
.core-orb strong{
  position:relative;margin-top:9px;
  color:var(--sc-ink);
  font-family:var(--sc-font);
  font-size:20px;
  font-weight:700;
  letter-spacing:.07em;
  text-shadow:0 0 16px rgba(42,201,255,.62);
}
.orb-code{
  position:relative;margin-top:6px;
  color:var(--sc-ink-3);
  font-family:var(--sc-font-mono);
  font-size:var(--sc-fs-code);
  letter-spacing:var(--sc-ls-code);
}
.core-orb b{
  position:relative;margin-top:11px;
  display:inline-flex;align-items:center;gap:6px;
  padding:4px 11px;border-radius:20px;
  color:var(--sc-mint);
  background:var(--sc-mint-soft);
  border:1px solid rgba(60,232,170,.42);
  font-family:var(--sc-font-num);
  font-size:var(--sc-fs-aux);
  font-weight:600;
}
.core-orb b i{
  width:6px;height:6px;border-radius:50%;
  background:currentColor;
  box-shadow:0 0 8px currentColor;
  animation:node-blink 2.4s ease-in-out infinite;
}
.core-orb b.degraded{
  color:var(--sc-medium);
  background:var(--sc-medium-soft);
  border-color:rgba(255,181,69,.44);
}

/* ---------- 四张能力卡 ---------- */
.capability{
  position:absolute;z-index:3;
  width:218px;
  display:flex;align-items:center;gap:11px;
  padding:11px 13px;
  border:1px solid var(--sc-line);
  border-radius:var(--sc-radius-sm);
  background:
    radial-gradient(120% 100% at 0 0,var(--sc-accent-soft),transparent 60%),
    linear-gradient(140deg,var(--sc-panel-3),rgba(6,24,42,0) 62%),
    var(--sc-panel);
  box-shadow:var(--sc-inset),var(--sc-depth);
}
.cap-icon{
  flex:none;width:36px;height:36px;
  display:grid;place-items:center;
  border-radius:var(--sc-radius-sm);
  color:#cdf3ff;
  background:linear-gradient(150deg,rgba(42,201,255,.22),rgba(10,110,168,.10));
  border:1px solid rgba(112,224,255,.34);
}
.cap-copy{min-width:0;display:flex;flex-direction:column;gap:5px}
.capability strong{
  color:var(--sc-ink);
  font-family:var(--sc-font);
  font-size:var(--sc-fs-body);
  font-weight:600;
  letter-spacing:.03em;
  white-space:nowrap;
}
.capability span{
  color:var(--sc-ink-4);
  font-family:var(--sc-font-mono);
  font-size:var(--sc-fs-code);
  letter-spacing:.10em;
  white-space:nowrap;
}
/* 指向核心的接线端点 */
.cap-node{
  position:absolute;top:50%;
  width:7px;height:7px;margin-top:-3.5px;
  border-radius:50%;
  background:var(--sc-cyan);
  box-shadow:0 0 10px var(--sc-cyan);
  animation:node-blink 2.6s ease-in-out infinite;
}
.top-left{left:9%;top:5%}.top-right{right:9%;top:5%}
.mid-left{left:1%;top:38%}.mid-right{right:1%;top:38%}
.bottom-left{left:9%;bottom:22%}.bottom-right{right:9%;bottom:22%}
.top-left .cap-node,.mid-left .cap-node,.bottom-left .cap-node{right:-13px}
.top-right .cap-node,.mid-right .cap-node,.bottom-right .cap-node{left:-13px}
.top-right,.mid-right,.bottom-right{flex-direction:row-reverse;text-align:right}
.top-right .cap-copy,.mid-right .cap-copy,.bottom-right .cap-copy{align-items:flex-end}

/* ---------- 处置链路 ---------- */
.decision-flow{
  position:absolute;left:4%;right:4%;bottom:4%;z-index:3;
  display:flex;align-items:center;justify-content:center;gap:10px;
}
.decision-flow span{
  padding:7px 13px;
  border-radius:var(--sc-radius-sm);
  color:var(--sc-ink-2);
  background:rgba(8,36,58,.82);
  border:1px solid var(--sc-line-2);
  box-shadow:var(--sc-inset);
  font-family:var(--sc-font);
  font-size:var(--sc-fs-aux);
  white-space:nowrap;
}
.decision-flow span.terminal{
  color:#d8f4ff;
  border-color:rgba(112,224,255,.42);
  box-shadow:var(--sc-inset),0 0 18px -6px rgba(42,201,255,.5);
}
/* 流动箭头：渐变沿连线推进，读作"数据在走" */
.decision-flow i{
  position:relative;width:30px;height:1px;
  background:linear-gradient(90deg,var(--sc-accent-deep),var(--sc-accent));
  box-shadow:0 0 7px rgba(42,201,255,.6);
}
.decision-flow i::after{
  content:'';position:absolute;right:-1px;top:-3px;
  border-left:5px solid var(--sc-accent);
  border-top:3px solid transparent;
  border-bottom:3px solid transparent;
}
.decision-flow i::before{
  content:'';position:absolute;left:0;top:-1px;
  width:7px;height:3px;border-radius:2px;
  background:#eafcff;
  box-shadow:0 0 8px #9ceeff;
  animation:flow-run 2.4s linear infinite;
}
.decision-flow i:nth-of-type(2)::before{animation-delay:-.8s}
.decision-flow i:nth-of-type(3)::before{animation-delay:-1.6s}

/* A shallow base makes the core read as an orchestration console, not a flat orb. */
.core-orb::after{content:'';position:absolute;left:10%;right:10%;bottom:-16px;height:28px;border:1px solid rgba(42,201,255,.38);border-top:0;border-radius:0 0 50% 50%;background:linear-gradient(180deg,rgba(28,133,181,.46),rgba(3,25,43,.1));box-shadow:0 11px 22px rgba(0,0,0,.32),0 0 18px rgba(42,201,255,.2)}
.core-orb::before{content:'';position:absolute;left:7%;right:7%;bottom:-8px;height:22px;border:1px solid rgba(112,224,255,.3);border-radius:50%;background:repeating-linear-gradient(90deg,rgba(42,201,255,.6) 0 9px,transparent 9px 17px);box-shadow:0 0 14px rgba(42,201,255,.26)}
.core-orb>*{z-index:1}

@keyframes orb-spin{to{transform:rotate(360deg)}}
@keyframes orb-scan{0%,100%{transform:translateY(-45%)}50%{transform:translateY(45%)}}
@keyframes node-blink{0%,100%{opacity:1}50%{opacity:.4}}
@keyframes flow-run{0%{left:0;opacity:0}18%{opacity:1}82%{opacity:1}100%{left:100%;opacity:0}}

/* ---------- 紧凑屏：等比收缩，标签保持可读 ---------- */
/* --core 由 syncOrbSize 按 coreGeometry 写成内联值，此处不再覆盖尺寸 */
@media(max-width:0px){
  .capability{padding:9px 11px;gap:9px}
  .cap-icon{width:32px;height:32px}
  .cap-icon :deep(svg){width:17px;height:17px}
  .decision-flow span{padding:6px 10px}
}
@media(max-width:0px){
  .orb-emblem{width:44px;height:44px}
  .orb-emblem :deep(svg){width:28px;height:28px}
  .core-orb strong{margin-top:6px}
  .core-orb b{margin-top:7px;padding:3px 9px}
  .top-left,.top-right{top:6%}
  .bottom-left,.bottom-right{bottom:21%}
  .decision-flow{bottom:2.5%;gap:7px}
}
@media(max-width:0px){
  /* 不覆盖 --core / --cy：两者由 coreGeometry 统一决定 */
  .capability{width:clamp(132px,13vw,158px);padding:8px 9px;gap:7px}
  .cap-icon{width:28px;height:28px}
  .cap-icon :deep(svg){width:15px;height:15px}
  .top-left,.bottom-left{left:1%}
  .top-right,.bottom-right{right:1%}
  .decision-flow{left:2%;right:2%;gap:6px}
  .decision-flow span{padding:5px 8px}
}
@media(prefers-reduced-motion:reduce){
  .orb-ring,.orb-scan,.cap-node,.core-orb b i,.decision-flow i::before{animation:none}
  .orb-scan{opacity:.3}
}

/* CockpitShell scales a fixed 1920x1080 scene; do not reflow its internal geometry per viewport. */
@media(max-width:0px){
  .capability{width:clamp(158px,15vw,218px);padding:11px 13px;gap:11px}
  .cap-icon{width:36px;height:36px}.cap-icon :deep(svg){width:20px;height:20px}
  .orb-emblem{width:56px;height:56px}.orb-emblem :deep(svg){width:38px;height:38px}
  .core-orb strong{margin-top:9px}.core-orb b{margin-top:11px;padding:4px 11px}
  .top-left,.top-right{top:9%}.bottom-left,.bottom-right{bottom:23%}
  .top-left,.bottom-left{left:3%}.top-right,.bottom-right{right:3%}
  .decision-flow{left:4%;right:4%;bottom:4%;gap:10px}.decision-flow span{padding:7px 13px}
}
</style>
