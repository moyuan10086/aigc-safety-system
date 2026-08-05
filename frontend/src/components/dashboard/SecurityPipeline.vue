<template>
  <div class="pipeline-stage">
    <svg class="flow-layer" viewBox="0 0 1000 540" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <filter id="flow-glow" x="-80%" y="-80%" width="260%" height="260%">
          <feGaussianBlur stdDeviation="4" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>
      <path id="flow-a" d="M 276 112 C 350 112, 376 216, 438 238" />
      <path id="flow-b" d="M 724 112 C 650 112, 624 216, 562 238" />
      <path id="flow-c" d="M 276 370 C 350 370, 376 286, 438 262" />
      <path id="flow-d" d="M 724 370 C 650 370, 624 286, 562 262" />
      <g class="flow-particles" filter="url(#flow-glow)">
        <circle r="4"><animateMotion dur="3.2s" repeatCount="indefinite"><mpath href="#flow-a" /></animateMotion></circle>
        <circle r="4"><animateMotion dur="3.8s" begin="-.8s" repeatCount="indefinite"><mpath href="#flow-b" /></animateMotion></circle>
        <circle r="4"><animateMotion dur="3.5s" begin="-1.6s" repeatCount="indefinite"><mpath href="#flow-c" /></animateMotion></circle>
        <circle r="4"><animateMotion dur="4s" begin="-2.1s" repeatCount="indefinite"><mpath href="#flow-d" /></animateMotion></circle>
      </g>
    </svg>
    <div class="orbital-grid"></div>
    <div class="orbit orbit-c"></div><div class="orbit orbit-b"></div><div class="orbit orbit-a"></div>
    <div class="orbit-tick tick-a"></div><div class="orbit-tick tick-b"></div><div class="orbit-tick tick-c"></div>
    <div class="platform-shadow"></div>
    <div class="pipeline-core">
      <ShieldCheck :size="34" />
      <strong>安全审核中枢</strong>
      <span>POLICY ORCHESTRATOR</span>
      <b>{{ configured }}/{{ total }} 引擎就绪</b>
    </div>
    <div v-for="item in capabilities" :key="item.code" class="capability" :class="item.position">
      <component :is="item.icon" :size="19" />
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
</script>

<style scoped>
.pipeline-stage{position:relative;height:100%;min-height:0;overflow:hidden;background:radial-gradient(circle at 50% 45%,rgba(49,198,220,.10),transparent 34%)}.pipeline-stage::before,.pipeline-stage::after{content:'';position:absolute;left:50%;top:45%;background:rgba(49,198,220,.20);transform:translate(-50%,-50%)}.pipeline-stage::before{width:64%;height:1px}.pipeline-stage::after{width:1px;height:58%}.flow-layer{position:absolute;inset:0;width:100%;height:100%;z-index:1;pointer-events:none}.flow-layer path{fill:none;stroke:rgba(49,198,220,.24);stroke-width:1.5;stroke-dasharray:6 9;vector-effect:non-scaling-stroke}.flow-particles{fill:#7de8f5}.orbit{position:absolute;left:50%;top:45%;border:1px solid rgba(49,198,220,.18);border-radius:50%;transform:translate(-50%,-50%)}.orbit-a{width:42%;aspect-ratio:1}.orbit-b{width:64%;aspect-ratio:1;animation:pulse 3.4s ease-in-out infinite}.pipeline-core{position:absolute;left:50%;top:45%;width:142px;aspect-ratio:1;display:flex;align-items:center;justify-content:center;flex-direction:column;color:#7de8f5;background:#0b2b3f;border:1px solid #31c6dc;border-radius:50%;box-shadow:0 0 35px rgba(49,198,220,.23);transform:translate(-50%,-50%);z-index:2}.pipeline-core::before{content:'';position:absolute;inset:8px;border:1px dashed rgba(125,232,245,.32);border-radius:50%;animation:rotate 16s linear infinite}.pipeline-core strong{margin-top:7px;color:#e7f9ff;font-size:12px}.pipeline-core span{margin-top:3px;color:#4f7d94;font:7px ui-monospace,monospace}.pipeline-core b{margin-top:8px;padding:3px 7px;color:#4ddeaa;background:rgba(77,222,170,.08);font:7px ui-monospace,monospace}.capability{position:absolute;width:150px;height:56px;display:flex;align-items:center;gap:9px;padding:0 11px;color:#31c6dc;background:#0a2639;border:1px solid #24536d;z-index:2}.capability::after{content:'';position:absolute;width:32px;height:1px;background:#31c6dc}.capability div{min-width:0;display:flex;flex-direction:column}.capability strong{color:#d9edf7;font-size:9px}.capability span{margin-top:4px;color:#52778b;font:7px ui-monospace,monospace}.capability i{position:absolute;width:6px;height:6px;border-radius:50%;background:#4ddeaa;box-shadow:0 0 8px #4ddeaa}.top-left{left:8%;top:16%}.top-left::after{right:-33px}.top-left i{right:-38px}.top-right{right:8%;top:16%}.top-right::after{left:-33px}.top-right i{left:-38px}.bottom-left{left:8%;bottom:23%}.bottom-left::after{right:-33px}.bottom-left i{right:-38px}.bottom-right{right:8%;bottom:23%}.bottom-right::after{left:-33px}.bottom-right i{left:-38px}.decision-flow{position:absolute;left:7%;right:7%;bottom:5%;height:30px;display:flex;align-items:center;justify-content:center;gap:10px;color:#7298ac;font-size:8px}.decision-flow span{padding:5px 8px;background:#092335;border:1px solid #1c465e;white-space:nowrap}.decision-flow i{width:20px;height:1px;background:#31c6dc;position:relative}.decision-flow i::after{content:'';position:absolute;right:-1px;top:-2px;border-left:4px solid #31c6dc;border-top:2px solid transparent;border-bottom:2px solid transparent}@keyframes pulse{50%{opacity:.35;transform:translate(-50%,-50%) scale(1.04)}}@keyframes rotate{to{transform:rotate(360deg)}}@media(max-height:700px){.pipeline-core{width:112px}.pipeline-core strong{font-size:10px}.pipeline-core b{margin-top:5px}.capability{width:126px;height:44px;padding:0 8px}.capability strong{font-size:8px}.top-left,.bottom-left{left:5%}.top-right,.bottom-right{right:5%}.top-left,.top-right{top:10%}.bottom-left,.bottom-right{bottom:18%}.decision-flow{bottom:2%;height:24px;gap:5px}.decision-flow span{padding:3px 5px}.decision-flow i{width:12px}}@media(prefers-reduced-motion:reduce){.orbit-b,.pipeline-core::before{animation:none}.flow-particles{display:none}}
.pipeline-stage{background:radial-gradient(ellipse at 50% 43%,rgba(46,206,232,.16),rgba(8,41,59,.04) 29%,transparent 62%)}.orbital-grid{position:absolute;inset:8% 13% 15%;border:1px solid rgba(43,139,172,.16);background:repeating-linear-gradient(0deg,transparent 0 19px,rgba(73,184,209,.07) 20px),repeating-linear-gradient(90deg,transparent 0 19px,rgba(73,184,209,.07) 20px);clip-path:polygon(50% 0,100% 50%,50% 100%,0 50%)}.orbit-c{width:78%;aspect-ratio:1;border-color:rgba(43,145,177,.16);box-shadow:inset 0 0 28px rgba(49,198,220,.05)}.orbit-tick{position:absolute;left:50%;top:45%;width:74%;aspect-ratio:1;border-radius:50%;transform:translate(-50%,-50%);pointer-events:none}.orbit-tick::after{content:'';position:absolute;top:-2px;left:50%;width:4px;height:4px;background:#78eff6;box-shadow:0 0 12px #78eff6}.tick-a{animation:orbit-spin 18s linear infinite}.tick-b{width:56%;animation:orbit-spin 12s linear infinite reverse}.tick-c{width:88%;animation:orbit-spin 27s linear infinite}.platform-shadow{position:absolute;left:50%;top:52%;width:200px;height:45px;border-radius:50%;border:1px solid rgba(63,216,234,.45);background:radial-gradient(ellipse,rgba(49,198,220,.28),rgba(49,198,220,.03) 62%,transparent 63%);box-shadow:0 0 34px rgba(49,198,220,.2);transform:translateX(-50%) perspective(120px) rotateX(61deg);z-index:1}.pipeline-core{background:radial-gradient(circle at 35% 25%,#15516b,#082b40 60%,#061c2d);border-color:#54e0ef;box-shadow:0 0 12px rgba(125,232,245,.8),0 0 48px rgba(49,198,220,.35),inset 0 0 24px rgba(130,238,248,.15)}.capability{background:linear-gradient(110deg,rgba(11,49,69,.94),rgba(7,28,43,.82));border-color:rgba(65,176,207,.62);clip-path:polygon(0 8px,8px 0,100% 0,100% calc(100% - 8px),calc(100% - 8px) 100%,0 100%)}.capability::after,.decision-flow i{box-shadow:0 0 8px #55e0ed}.capability::after,.decision-flow i{background:#55e0ed}.capability strong{color:#e2f8ff}.decision-flow span{background:rgba(7,35,51,.78);border-color:rgba(55,132,162,.65);box-shadow:inset 0 1px rgba(112,223,239,.1)}@keyframes orbit-spin{to{transform:translate(-50%,-50%) rotate(360deg)}}@media(max-height:700px){.platform-shadow{width:165px}}@media(prefers-reduced-motion:reduce){.orbit-tick{animation:none}}
</style>
