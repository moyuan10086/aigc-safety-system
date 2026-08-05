<template>
  <div class="pipeline-stage">
    <div class="stage-glow"></div>
    <div class="stage-grid"></div>

    <!-- thin data paths: capability cards -> core junction nodes -->
    <svg class="flow-layer" viewBox="0 0 1000 600" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <filter id="flow-glow" x="-80%" y="-80%" width="260%" height="260%">
          <feGaussianBlur stdDeviation="3.4" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>
      <path id="flow-a" d="M 250 105 C 322 105, 344 150, 394 161" />
      <path id="flow-b" d="M 750 105 C 678 105, 656 150, 606 161" />
      <path id="flow-c" d="M 250 453 C 322 453, 344 396, 394 367" />
      <path id="flow-d" d="M 750 453 C 678 453, 656 396, 606 367" />
      <g class="flow-particles" filter="url(#flow-glow)">
        <circle r="4.2"><animateMotion dur="3.2s" repeatCount="indefinite"><mpath href="#flow-a" /></animateMotion></circle>
        <circle r="4.2"><animateMotion dur="3.8s" begin="-.8s" repeatCount="indefinite"><mpath href="#flow-b" /></animateMotion></circle>
        <circle r="4.2"><animateMotion dur="3.5s" begin="-1.6s" repeatCount="indefinite"><mpath href="#flow-c" /></animateMotion></circle>
        <circle r="4.2"><animateMotion dur="4s" begin="-2.1s" repeatCount="indefinite"><mpath href="#flow-d" /></animateMotion></circle>
      </g>
    </svg>

    <!-- 3 concentric energy rings + radial dotted tracks + 8 junction nodes -->
    <div class="ring ring-3"></div>
    <div class="ring ring-2"></div>
    <div class="ring ring-1"></div>
    <div class="ring-sweep"></div>
    <div class="ring-pulse"></div>
    <div class="tracks">
      <i v-for="angle in trackAngles" :key="angle" :style="{ '--a': angle + 'deg' }"></i>
    </div>
    <div class="junctions">
      <b
        v-for="node in junctions"
        :key="node.angle"
        :class="{ major: node.major }"
        :style="{ '--a': node.angle + 'deg' }"
      ></b>
    </div>

    <div class="platform"></div>

    <div class="pipeline-core">
      <span class="core-scan"></span>
      <ShieldCheck class="core-icon" :size="40" />
      <strong>安全审核中枢</strong>
      <span class="core-code">POLICY ORCHESTRATOR</span>
      <b>引擎 {{ configured }}/{{ total }} 在线</b>
    </div>

    <div v-for="item in capabilities" :key="item.code" class="capability" :class="item.position">
      <span class="cap-icon"><component :is="item.icon" :size="22" /></span>
      <div><strong>{{ item.label }}</strong><span>{{ item.code }}</span></div>
      <i></i>
    </div>

    <div class="decision-flow">
      <span>输入采集</span><i></i><span>多模态判定</span><i></i><span>策略融合</span><i></i><span>放行 / 复核 / 阻断</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { BadgeCheck, ScanFace, ScanSearch, ShieldCheck, UserCheck } from 'lucide-vue-next'

defineProps<{ configured: number; total: number }>()

const capabilities = [
  { label: '真实性检测', code: 'DEEPFAKE / MLLM', icon: ScanFace, position: 'top-left' },
  { label: '内容安全审核', code: 'VISION / RAG', icon: ScanSearch, position: 'top-right' },
  { label: '来源与取证', code: 'C2PA / HASH', icon: BadgeCheck, position: 'bottom-left' },
  { label: '人工复核闭环', code: 'HUMAN REVIEW', icon: UserCheck, position: 'bottom-right' },
]

const trackAngles = [0, 45, 90, 135, 180, 225, 270, 315]
// 8 junction nodes; the four diagonals sit on the capability data paths
const junctions = trackAngles.map((angle) => ({ angle, major: angle % 90 === 45 }))
</script>

<style scoped>
.pipeline-stage{
  --core:218px;
  --r1:calc(var(--core) * 1.2);
  --r2:calc(var(--core) * 1.52);
  --r3:calc(var(--core) * 1.9);
  --cx:50%;
  --cy:44%;
  --blue:#3fd2ff;
  --blue-soft:rgba(63,210,255,.22);
  --ink:#e9fbff;
  position:relative;height:100%;min-height:0;overflow:hidden;
  background:
    radial-gradient(ellipse 60% 50% at 50% 44%,rgba(30,120,190,.16),transparent 70%),
    linear-gradient(180deg,#05192a,#04121f 62%,#030d18);
}
/* backdrop: bright core halo over deep navy for strong light/dark separation */
.stage-glow{position:absolute;left:var(--cx);top:var(--cy);width:calc(var(--r3) * 1.5);aspect-ratio:1;border-radius:50%;transform:translate(-50%,-50%);pointer-events:none;
  background:radial-gradient(circle,rgba(93,226,255,.20),rgba(35,150,210,.08) 42%,transparent 68%)}
.stage-grid{position:absolute;inset:6% 11% 13%;pointer-events:none;
  border:1px solid rgba(63,160,200,.18);
  background:
    repeating-linear-gradient(0deg,transparent 0 25px,rgba(84,190,220,.07) 26px),
    repeating-linear-gradient(90deg,transparent 0 25px,rgba(84,190,220,.07) 26px);
  clip-path:polygon(50% 0,100% 50%,50% 100%,0 50%)}
.pipeline-stage::before,.pipeline-stage::after{content:'';position:absolute;left:var(--cx);top:var(--cy);background:linear-gradient(90deg,transparent,rgba(63,210,255,.26),transparent);transform:translate(-50%,-50%);pointer-events:none}
.pipeline-stage::before{width:72%;height:1px}
.pipeline-stage::after{width:1px;height:64%;background:linear-gradient(180deg,transparent,rgba(63,210,255,.26),transparent)}

.flow-layer{position:absolute;inset:0;width:100%;height:100%;z-index:2;pointer-events:none}
.flow-layer path{fill:none;stroke:rgba(96,214,250,.42);stroke-width:1.4;stroke-dasharray:5 8;vector-effect:non-scaling-stroke}
.flow-particles{fill:#b6f2ff}

/* ---- three concentric energy rings ---- */
.ring,.ring-sweep,.ring-pulse,.tracks,.junctions{position:absolute;left:var(--cx);top:var(--cy);aspect-ratio:1;border-radius:50%;transform:translate(-50%,-50%);pointer-events:none}
.ring-1{width:var(--r1);border:1px solid rgba(94,222,255,.55);box-shadow:0 0 18px rgba(63,210,255,.28),inset 0 0 22px rgba(63,210,255,.12)}
.ring-2{width:var(--r2);border:1px dashed rgba(78,196,236,.40);animation:ring-spin 34s linear infinite}
.ring-3{width:var(--r3);border:1px solid rgba(58,150,196,.30);box-shadow:inset 0 0 46px rgba(63,210,255,.06)}
/* rotating conic sweep gives the rings their "energy" read */
.ring-sweep{width:var(--r2);
  background:conic-gradient(from 0deg,transparent 0 62%,rgba(63,210,255,.16) 84%,rgba(150,240,255,.34) 96%,transparent);
  mask:radial-gradient(circle,transparent 0 calc(50% - 15px),#000 calc(50% - 14px) 50%,transparent 51%);
  -webkit-mask:radial-gradient(circle,transparent 0 calc(50% - 15px),#000 calc(50% - 14px) 50%,transparent 51%);
  animation:ring-spin 7.5s linear infinite}
.ring-pulse{width:var(--r1);border:1px solid rgba(150,240,255,.5);animation:ring-emit 4.2s ease-out infinite}

/* ---- radial dotted tracks ---- */
.tracks{width:var(--r3)}
.tracks i{position:absolute;left:50%;top:50%;width:1px;height:50%;transform-origin:top center;transform:translateX(-50%) rotate(var(--a));
  background:repeating-linear-gradient(180deg,rgba(120,226,255,.52) 0 3px,transparent 3px 9px)}

/* ---- 8 glowing junction nodes on the inner ring ---- */
.junctions{width:var(--r1);z-index:3}
.junctions b{position:absolute;left:50%;top:50%;width:9px;height:9px;margin:-4.5px;border-radius:50%;
  background:#d3f6ff;box-shadow:0 0 10px #6fe3ff,0 0 22px rgba(63,210,255,.7);
  transform:rotate(var(--a)) translateY(calc(var(--r1) / -2)) rotate(calc(var(--a) * -1));
  animation:node-blink 2.6s ease-in-out infinite}
.junctions b.major{width:13px;height:13px;margin:-6.5px;background:#eafcff;border:2px solid #3fd2ff;box-shadow:0 0 14px #6fe3ff,0 0 30px rgba(63,210,255,.75)}
.junctions b:nth-child(2){animation-delay:-.3s}.junctions b:nth-child(3){animation-delay:-.6s}
.junctions b:nth-child(4){animation-delay:-.9s}.junctions b:nth-child(5){animation-delay:-1.2s}
.junctions b:nth-child(6){animation-delay:-1.5s}.junctions b:nth-child(7){animation-delay:-1.8s}
.junctions b:nth-child(8){animation-delay:-2.1s}

/* ---- low elliptical platform beneath the core ---- */
.platform{position:absolute;left:var(--cx);top:calc(var(--cy) + var(--core) / 2 - 6px);width:calc(var(--core) * 1.34);height:calc(var(--core) * .34);
  border-radius:50%;transform:translate(-50%,-50%);pointer-events:none;z-index:1;
  border:1px solid rgba(96,220,255,.42);
  background:radial-gradient(ellipse at 50% 42%,rgba(84,214,255,.30),rgba(46,168,220,.08) 58%,transparent 72%);
  box-shadow:0 0 40px rgba(63,210,255,.24),inset 0 0 26px rgba(63,210,255,.16)}
.platform::after{content:'';position:absolute;left:50%;top:50%;width:64%;height:52%;border-radius:50%;transform:translate(-50%,-50%);
  border:1px solid rgba(150,240,255,.35)}

/* ---- vivid electric-blue security core (~250px @1080p) ---- */
.pipeline-core{position:absolute;left:var(--cx);top:var(--cy);width:var(--core);aspect-ratio:1;z-index:4;
  display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;
  border-radius:50%;transform:translate(-50%,-50%);color:#a9edff;
  background:
    radial-gradient(circle at 34% 24%,rgba(120,232,255,.34),transparent 52%),
    radial-gradient(circle at 50% 50%,#12628a 0%,#0a3a58 46%,#06223a 74%,#041625 100%);
  border:2px solid #5fdcff;
  box-shadow:0 0 0 6px rgba(63,210,255,.09),0 0 26px rgba(120,232,255,.55),0 0 74px rgba(63,210,255,.34),inset 0 0 40px rgba(130,238,255,.20)}
.pipeline-core::before{content:'';position:absolute;inset:11px;border-radius:50%;border:1px dashed rgba(160,240,255,.42);animation:ring-spin 18s linear infinite}
.pipeline-core::after{content:'';position:absolute;inset:20px;border-radius:50%;border:1px solid rgba(63,210,255,.22)}
.core-scan{position:absolute;inset:11px;border-radius:50%;overflow:hidden;
  background:linear-gradient(180deg,transparent 46%,rgba(170,245,255,.30) 50%,transparent 54%);
  animation:core-scan 3.6s ease-in-out infinite}
.core-icon{color:#c9f5ff;filter:drop-shadow(0 0 10px rgba(120,232,255,.85))}
.pipeline-core strong{position:relative;margin-top:10px;color:var(--ink);font-size:17px;font-weight:700;letter-spacing:.06em;text-shadow:0 0 14px rgba(63,210,255,.6)}
.core-code{position:relative;margin-top:5px;color:#7fbcd8;font:9px/1 ui-monospace,monospace;letter-spacing:.14em}
.pipeline-core b{position:relative;margin-top:11px;padding:4px 10px;border-radius:2px;color:#63f2c0;
  background:rgba(77,222,170,.10);border:1px solid rgba(77,222,170,.42);font:11px ui-monospace,monospace}

/* ---- four symmetric capability cards ---- */
.capability{position:absolute;width:210px;height:74px;z-index:3;
  display:flex;align-items:center;gap:11px;padding:0 13px;color:#6fe3ff;
  background:linear-gradient(112deg,rgba(13,58,84,.95),rgba(6,29,46,.86));
  border:1px solid rgba(84,196,232,.62);
  box-shadow:0 0 22px rgba(8,40,62,.7),inset 0 1px rgba(150,240,255,.14);
  clip-path:polygon(0 10px,10px 0,100% 0,100% calc(100% - 10px),calc(100% - 10px) 100%,0 100%)}
.cap-icon{flex:none;width:38px;height:38px;display:grid;place-items:center;border-radius:3px;
  color:#bdf1ff;background:rgba(63,210,255,.12);border:1px solid rgba(84,196,232,.5)}
.capability div{min-width:0;display:flex;flex-direction:column}
.capability strong{color:#eafaff;font-size:14px;font-weight:650;letter-spacing:.04em;white-space:nowrap}
.capability span{margin-top:5px;color:#6d9db5;font:9px ui-monospace,monospace;letter-spacing:.08em}
/* connector stub + pulsing endpoint toward the core */
.capability::after{content:'';position:absolute;top:50%;width:34px;height:1px;background:#5fdcff;box-shadow:0 0 8px #5fdcff}
.capability i{position:absolute;top:50%;width:7px;height:7px;margin-top:-3.5px;border-radius:50%;
  background:#63f2c0;box-shadow:0 0 10px #63f2c0;animation:node-blink 2.4s ease-in-out infinite}
.top-left{left:4%;top:11%}.top-right{right:4%;top:11%}
.bottom-left{left:4%;bottom:22%}.bottom-right{right:4%;bottom:22%}
.top-left::after,.bottom-left::after{right:-35px}
.top-left i,.bottom-left i{right:-42px}
.top-right::after,.bottom-right::after{left:-35px}
.top-right i,.bottom-right i{left:-42px}

/* ---- decision flow strip (unchanged order) ---- */
.decision-flow{position:absolute;left:5%;right:5%;bottom:5%;z-index:3;
  display:flex;align-items:center;justify-content:center;gap:12px;color:#8fb5c8;font-size:11px}
.decision-flow span{padding:7px 12px;color:#cfeaf7;background:rgba(8,40,60,.82);
  border:1px solid rgba(72,158,192,.62);box-shadow:inset 0 1px rgba(140,232,250,.12);white-space:nowrap}
.decision-flow i{position:relative;width:26px;height:1px;background:#5fdcff;box-shadow:0 0 8px #5fdcff}
.decision-flow i::after{content:'';position:absolute;right:-1px;top:-3px;border-left:5px solid #5fdcff;border-top:3px solid transparent;border-bottom:3px solid transparent}

@keyframes ring-spin{to{transform:translate(-50%,-50%) rotate(360deg)}}
@keyframes ring-emit{0%{opacity:.85;transform:translate(-50%,-50%) scale(.98)}70%,100%{opacity:0;transform:translate(-50%,-50%) scale(1.55)}}
@keyframes node-blink{0%,100%{opacity:1}50%{opacity:.42}}
@keyframes core-scan{0%,100%{transform:translateY(-46%)}50%{transform:translateY(46%)}}

/* ---- compact heights: shrink proportionally, keep labels legible ---- */
@media(max-height:820px){.pipeline-stage{--core:210px}
  .pipeline-core strong{font-size:15px}.pipeline-core b{font-size:10px;margin-top:8px}
  .capability{width:188px;height:66px}.capability strong{font-size:13px}}
@media(max-height:700px){.pipeline-stage{--core:172px;--cy:43%}
  .core-icon{width:30px;height:30px}
  .pipeline-core strong{margin-top:7px;font-size:13px}.core-code{font-size:8px}
  .pipeline-core b{margin-top:6px;padding:3px 7px;font-size:9px}
  .capability{width:166px;height:58px;gap:9px;padding:0 10px}
  .cap-icon{width:32px;height:32px}
  .capability strong{font-size:12px}.capability span{font-size:8px;margin-top:3px}
  .top-left,.top-right{top:8%}.bottom-left,.bottom-right{bottom:20%}
  .decision-flow{bottom:3%;gap:8px;font-size:10px}
  .decision-flow span{padding:5px 8px}.decision-flow i{width:18px}}

@media(prefers-reduced-motion:reduce){
  .ring-2,.ring-sweep,.ring-pulse,.pipeline-core::before,.core-scan,.junctions b,.capability i{animation:none}
  .ring-pulse{opacity:.35}
  .flow-particles{display:none}}
</style>
