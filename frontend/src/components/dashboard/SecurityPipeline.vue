<template>
  <section class="pipeline-stage" :class="{ 'is-alert': alert }" aria-label="安全审核中枢能力拓扑">
    <section class="core-stage-frame" aria-label="安全审核中枢环形舞台">
      <AiCoreCanvas class="core-energy" :intensity="intensity" :alert="alert" />
      <span class="stage-grid" aria-hidden="true"></span>

      <svg class="topology" viewBox="0 0 1000 680" preserveAspectRatio="none" aria-hidden="true">
        <g v-for="item in capabilities" :key="`${item.code}-path`" :class="['topology-lane', item.position]">
          <path class="lane-base" :d="item.path" />
          <path class="lane-flow" :d="item.path" />
          <circle class="lane-runner" r="4"><animateMotion :dur="`${cycleSeconds}s`" repeatCount="indefinite" :begin="`${item.delay}s`" :path="item.path" /></circle>
        </g>
      </svg>
      <svg class="planetary-orbits" viewBox="0 0 1000 680" preserveAspectRatio="none" aria-hidden="true">
        <ellipse cx="500" cy="313" rx="370" ry="211" />
        <ellipse cx="500" cy="313" rx="305" ry="174" />
      </svg>

      <article class="core-shell">
        <span class="core-beam" aria-hidden="true"></span>
        <span class="core-shadow" aria-hidden="true"></span>
        <span class="core-3d" aria-hidden="true"><AiCoreScene :alert="alert" /></span>
        <span class="shield-pedestal" aria-hidden="true"></span>
        <span class="shield-stand"><HolographicShield /></span>
        <section class="core-copy">
          <strong>安全审核中枢</strong>
          <span class="orb-code">POLICY ORCHESTRATOR</span>
          <b :class="{ degraded: configured < total }"><i aria-hidden="true"></i>{{ configured }}/{{ total }} 引擎在线</b>
        </section>
      </article>

      <article v-for="item in capabilities" :key="item.code" class="capability" :class="[item.position, item.side]" :style="{ '--orbit-delay': `${item.orbitDelay}s` }">
        <span class="cap-orbit-body">
          <span class="cap-icon"><component :is="item.icon" :size="34" /></span>
          <section class="cap-copy">
            <strong>{{ item.label }}</strong>
            <span>{{ item.code }}</span>
            <small>{{ item.detail }}</small>
          </section>
          <i class="cap-node" aria-hidden="true"></i>
        </span>
      </article>

      <nav class="decision-flow" aria-label="安全审核处置链路">
        <span>输入采集</span><i aria-hidden="true"></i>
        <span>多模态判定</span><i aria-hidden="true"></i>
        <span>策略融合</span><i aria-hidden="true"></i>
        <span class="terminal">放行 / 复核 / 阻断</span>
      </nav>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { BookOpenCheck, Boxes, BrainCircuit, ScanFace, ShieldAlert, ShieldCheck } from 'lucide-vue-next'
import AiCoreCanvas from './AiCoreCanvas.vue'
import AiCoreScene from './AiCoreScene.vue'
import HolographicShield from './HolographicShield.vue'

const props = withDefaults(defineProps<{
  configured: number
  total: number
  alert?: boolean
}>(), { alert: false })

const intensity = computed(() => {
  if (!props.total) return 0.35
  return 0.35 + (props.configured / props.total) * 0.6
})

const cycleSeconds = 6
const capabilities = [
  { label: 'Deepfake 检测', code: 'DEEPFAKE / MLLM', detail: '真实性检测链路', icon: BrainCircuit, position: 'top-left', side: 'left', path: 'M 305 128 Q 385 170 447 254', delay: 0, orbitDelay: 0 },
  { label: 'MLLM 理解分析', code: 'POLICY / LLM', detail: '多模态语义策略', icon: ScanFace, position: 'top-right', side: 'right', path: 'M 695 128 Q 615 170 553 254', delay: -1, orbitDelay: -4 },
  { label: '实时防护', code: 'AUDIT / GUARDRAIL', detail: '实时审计与拦截', icon: ShieldCheck, position: 'mid-left', side: 'left', path: 'M 235 312 Q 335 312 420 312', delay: -2, orbitDelay: -8 },
  { label: 'RAG 内容审核', code: 'RAG / KNOWLEDGE', detail: '检索增强审核链路', icon: BookOpenCheck, position: 'mid-right', side: 'right', path: 'M 765 312 Q 665 312 580 312', delay: -3, orbitDelay: -12 },
  { label: '风险处置', code: 'REVIEW / ESCALATION', detail: '人工复核与处置', icon: ShieldAlert, position: 'bottom-left', side: 'left', path: 'M 305 500 Q 385 452 447 374', delay: -4, orbitDelay: -16 },
  { label: '样本与取证', code: 'C2PA / HASH', detail: '溯源证据索引', icon: Boxes, position: 'bottom-right', side: 'right', path: 'M 695 500 Q 615 452 553 374', delay: -5, orbitDelay: -20 },
]
</script>

<style scoped>
.pipeline-stage{
  position:relative;flex:1;min-height:0;display:flex;align-items:stretch;justify-content:center;overflow:hidden;padding:8px 10px 10px;
  background:radial-gradient(ellipse 58% 56% at 50% 46%,rgba(0,83,204,.16),transparent 68%),linear-gradient(180deg,rgba(2,17,39,.18),rgba(1,8,22,.34));
}
.pipeline-stage::before{content:'';position:absolute;inset:0;z-index:0;pointer-events:none;background:radial-gradient(circle,rgba(79,164,255,.34) 0 1px,transparent 1.5px) 0 0/31px 31px,radial-gradient(ellipse 48% 34% at 50% 47%,transparent 0 46%,rgba(28,111,236,.10) 46.4% 46.8%,transparent 47.2% 60%,rgba(28,111,236,.055) 60.4% 60.7%,transparent 61%);mask-image:radial-gradient(ellipse 72% 68% at 50% 48%,#000 5%,transparent 82%);opacity:.38}
.pipeline-stage::after{content:'';position:absolute;left:16%;right:16%;top:47%;height:1px;z-index:0;pointer-events:none;background:linear-gradient(90deg,transparent,rgba(49,132,255,.22),rgba(106,194,255,.38),rgba(49,132,255,.22),transparent);box-shadow:0 0 14px rgba(22,106,255,.16)}
.core-stage-frame{z-index:1}
.core-stage-frame{
  --cx:50%;--cy:46%;--node-w:180px;
  position:relative;width:min(100%,900px);height:100%;min-height:0;overflow:hidden;
  border:1px solid rgba(59,145,232,.13);border-radius:4px;
  background:radial-gradient(ellipse 42% 38% at var(--cx) var(--cy),rgba(0,91,224,.22),transparent 72%),radial-gradient(ellipse 88% 72% at 50% 52%,rgba(5,34,77,.22),transparent 76%),linear-gradient(180deg,rgba(3,20,45,.58),rgba(1,8,22,.72));
  box-shadow:inset 0 0 76px rgba(0,34,90,.18),0 0 24px rgba(0,58,145,.06);
}
.core-stage-frame::before{content:'';position:absolute;inset:7px;z-index:8;pointer-events:none;background:linear-gradient(#45caff,#45caff) 0 0/28px 1px no-repeat,linear-gradient(#45caff,#45caff) 0 0/1px 28px no-repeat,linear-gradient(#45caff,#45caff) 100% 0/28px 1px no-repeat,linear-gradient(#45caff,#45caff) 100% 0/1px 28px no-repeat,linear-gradient(#45caff,#45caff) 0 100%/28px 1px no-repeat,linear-gradient(#45caff,#45caff) 0 100%/1px 28px no-repeat,linear-gradient(#45caff,#45caff) 100% 100%/28px 1px no-repeat,linear-gradient(#45caff,#45caff) 100% 100%/1px 28px no-repeat;opacity:.45}
.core-stage-frame::after{content:'';position:absolute;inset:0;z-index:0;pointer-events:none;background:linear-gradient(rgba(42,126,224,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(42,126,224,.035) 1px,transparent 1px),radial-gradient(circle at 50% 46%,transparent 0 28%,rgba(32,119,255,.05) 28.3% 28.6%,transparent 29% 100%);background-size:42px 42px,42px 42px,100% 100%;mask-image:radial-gradient(ellipse 72% 65% at 50% 48%,#000 20%,transparent 82%);opacity:.78}
.core-energy{z-index:1}
.stage-grid{
  position:absolute;left:12%;right:12%;top:10%;bottom:13%;z-index:1;pointer-events:none;
  background:repeating-linear-gradient(0deg,transparent 0 31px,var(--sc-grid-major) 32px),repeating-linear-gradient(90deg,transparent 0 31px,var(--sc-grid-major) 32px);
  clip-path:polygon(50% 0,100% 50%,50% 100%,0 50%);opacity:.20;transform:perspective(520px) rotateX(58deg) scaleY(.72);transform-origin:50% 58%;
}

.core-shell{
  position:absolute;left:var(--cx);top:var(--cy);z-index:4;width:340px;height:300px;
  transform:translate(-50%,-50%) scale(.92);pointer-events:none;filter:drop-shadow(0 24px 28px rgba(0,34,100,.28));
}
.core-beam{position:absolute;left:50%;top:-62px;width:5px;height:382px;transform:translateX(-50%);background:linear-gradient(180deg,transparent,rgba(42,150,255,.04) 12%,rgba(90,205,255,.64) 45%,rgba(42,150,255,.18) 70%,transparent);filter:blur(2px);opacity:.78;box-shadow:0 0 22px rgba(22,140,255,.32)}
.core-shadow{position:absolute;left:50%;bottom:7px;width:322px;height:58px;transform:translateX(-50%);border-radius:50%;background:rgba(0,0,0,.48);filter:blur(14px)}
.core-3d{position:absolute;left:0;top:-58px;width:100%;bottom:-36px;z-index:3}
.shield-pedestal{position:absolute;left:50%;top:161px;z-index:9;width:170px;height:42px;clip-path:polygon(14% 0,86% 0,100% 50%,82% 100%,18% 100%,0 50%);background:linear-gradient(180deg,rgba(105,211,255,.20),rgba(7,65,151,.08));box-shadow:inset 0 0 0 1px rgba(96,196,255,.42),0 0 30px rgba(22,140,255,.38);transform:translateX(-50%) perspective(180px) rotateX(61deg);transform-origin:50% 50%;backdrop-filter:blur(8px)}
.shield-pedestal::before{content:'';position:absolute;inset:8px 22px;border:1px solid rgba(114,217,255,.52);border-radius:50%;box-shadow:0 0 18px rgba(22,140,255,.46)}
.shield-pedestal::after{content:'';position:absolute;left:50%;top:-46px;width:2px;height:52px;transform:translateX(-50%);background:linear-gradient(180deg,rgba(114,217,255,.08),rgba(114,217,255,.58));filter:blur(.4px);box-shadow:0 0 8px rgba(22,140,255,.52)}
.shield-stand{position:absolute;left:50%;top:7px;z-index:10;width:146px;height:180px;display:block;background:transparent;transform:translateX(-50%);transform-origin:50% 100%;animation:shield-hover 5.2s ease-in-out infinite}
.shield-stand :deep(.holographic-shield){width:100%;height:100%}
@keyframes shield-hover{0%,100%{transform:translateX(-50%) translateY(2px)}50%{transform:translateX(-50%) translateY(-5px)}}
.core-copy{position:absolute;left:50%;top:205px;z-index:12;width:250px;display:flex;transform:translateX(-50%);flex-direction:column;align-items:center;text-align:center}
.core-copy strong{position:relative;color:var(--sc-ink);font:700 18px var(--sc-font);text-shadow:0 0 12px rgba(42,150,255,.42)}
.orb-code{position:relative;margin-top:5px;color:var(--sc-ink-3);font:var(--sc-fs-code) var(--sc-font-mono);letter-spacing:var(--sc-ls-code)}
.core-copy b{position:relative;margin-top:10px;display:inline-flex;align-items:center;gap:7px;padding:4px 13px;border:1px solid rgba(60,232,170,.42);border-radius:18px;color:var(--sc-mint);background:var(--sc-mint-soft);font:600 var(--sc-fs-aux) var(--sc-font-num)}
.core-copy b i{width:6px;height:6px;border-radius:50%;background:currentColor;box-shadow:0 0 8px currentColor;animation:node-blink 2.4s ease-in-out infinite}
.core-copy b.degraded{color:var(--sc-medium);background:var(--sc-medium-soft);border-color:rgba(255,181,69,.44)}

.capability{
  position:absolute;left:0;top:0;right:auto;bottom:auto;z-index:5;width:var(--node-w);min-height:68px;
  offset-path:ellipse(37% 31% at 50% 46%);offset-rotate:0deg;animation:planetary-orbit 24s linear infinite;animation-delay:var(--orbit-delay);
}
.cap-orbit-body{
  position:relative;width:100%;min-height:68px;display:flex;align-items:center;gap:12px;padding:8px 12px;
  border:1px solid rgba(62,145,255,.15);border-radius:3px;background:linear-gradient(100deg,rgba(4,27,65,.72),rgba(2,13,34,.76));
  backdrop-filter:blur(8px);box-shadow:inset 0 0 18px rgba(32,119,255,.045),0 8px 20px rgba(0,7,22,.28);
}
.cap-orbit-body::after{content:'';position:absolute;left:68px;right:12px;top:34px;height:1px;background:linear-gradient(90deg,rgba(74,166,214,.24),transparent)}
.cap-icon{
  position:relative;flex:0 0 54px;width:54px;height:54px;display:grid;place-items:center;
  clip-path:polygon(50% 0,93% 24%,93% 76%,50% 100%,7% 76%,7% 24%);color:var(--sc-accent);
  background:var(--sc-accent);filter:drop-shadow(0 0 9px rgba(22,140,255,.34));
}
.cap-icon::before,.cap-icon::after{content:'';position:absolute;clip-path:inherit}
.cap-icon::before{inset:2px;background:linear-gradient(145deg,rgba(8,66,96,.98),rgba(3,24,42,.98))}
.cap-icon::after{inset:8px;background:linear-gradient(145deg,rgba(16,100,134,.34),rgba(3,25,44,.12));box-shadow:inset 0 0 0 1px var(--sc-line-hi)}
.cap-icon :deep(svg){position:relative;z-index:2;width:26px;height:26px;stroke-width:1.5;filter:drop-shadow(0 0 6px rgba(34,227,216,.60))}
.cap-copy{min-width:0;display:flex;flex:1;flex-direction:column;align-items:flex-start;gap:3px}
.capability strong{color:var(--sc-ink);font:650 14px var(--sc-font);white-space:nowrap;text-shadow:0 0 10px rgba(64,158,255,.18)}
.capability .cap-copy>span{color:var(--sc-ink-2);font:var(--sc-fs-code) var(--sc-font-mono);letter-spacing:.08em;white-space:nowrap}
.capability small{color:var(--sc-ink-3);font-size:11px;line-height:1.25;white-space:nowrap}
.cap-node{position:absolute;top:50%;right:-5px;width:7px;height:7px;margin-top:-3px;border-radius:50%;background:var(--sc-cyan);box-shadow:0 0 10px var(--sc-cyan);animation:node-blink 2.6s ease-in-out infinite}
.top-left{left:12%;top:6%}.top-right{right:12%;top:6%}
.mid-left{left:4%;top:41%}.mid-right{right:4%;top:41%}
.bottom-left{left:12%;bottom:15%}.bottom-right{right:12%;bottom:15%}
.capability.top-left,.capability.top-right,.capability.mid-left,.capability.mid-right,.capability.bottom-left,.capability.bottom-right{left:0;right:auto;top:0;bottom:auto}
.capability.right .cap-orbit-body{flex-direction:row}
.capability.right .cap-copy{align-items:flex-start;text-align:left}
.capability.right .cap-orbit-body::after{left:68px;right:12px;background:linear-gradient(90deg,rgba(74,166,214,.24),transparent)}
.capability.right .cap-node{left:auto;right:-5px}

.topology{position:absolute;inset:0;z-index:2;width:100%;height:100%;pointer-events:none;overflow:visible}
.planetary-orbits{position:absolute;inset:0;z-index:2;width:100%;height:100%;pointer-events:none;overflow:visible}
.planetary-orbits ellipse{fill:none;stroke:rgba(58,153,255,.24);stroke-width:1;stroke-dasharray:3 8;vector-effect:non-scaling-stroke;filter:drop-shadow(0 0 4px rgba(22,140,255,.32))}
.topology-lane path{fill:none;vector-effect:non-scaling-stroke}
.lane-base{stroke:rgba(42,151,255,.24);stroke-width:1}
.lane-flow{stroke:rgba(91,211,255,.78);stroke-width:1.4;stroke-linecap:round;stroke-dasharray:3 13;animation:lane-cycle 6s linear infinite;filter:drop-shadow(0 0 4px rgba(42,173,255,.72))}
.lane-runner{fill:#d9f8ff;filter:drop-shadow(0 0 7px #2aa8ff)}

.decision-flow{
  position:absolute;left:50%;bottom:clamp(42px,10%,96px);z-index:6;display:flex;align-items:center;justify-content:center;gap:7px;
  padding:10px 18px;transform:translateX(-50%);border-top:1px solid rgba(54,166,255,.22);border-bottom:1px solid rgba(54,166,255,.12);
  background:linear-gradient(90deg,transparent,rgba(5,33,62,.58) 12%,rgba(6,41,76,.68) 50%,rgba(5,33,62,.58) 88%,transparent);
}
.decision-flow::before{content:'';position:absolute;left:50%;top:-28px;width:1px;height:28px;background:linear-gradient(transparent,rgba(64,177,255,.54));box-shadow:0 0 7px rgba(42,151,255,.45)}
.decision-flow span{padding:7px 12px;border:1px solid rgba(76,172,229,.22);border-radius:2px;color:var(--sc-ink-2);background:linear-gradient(180deg,rgba(15,57,91,.56),rgba(5,28,52,.42));font:600 13px var(--sc-font);white-space:nowrap;box-shadow:inset 0 1px rgba(119,210,255,.06)}
.decision-flow .terminal{color:var(--sc-ink);border-color:rgba(76,196,255,.52);background:linear-gradient(180deg,rgba(16,75,115,.72),rgba(5,34,63,.58));font-size:14px;font-weight:700;box-shadow:inset 0 0 14px rgba(42,151,255,.12),0 0 14px rgba(22,140,255,.12);text-shadow:0 0 9px rgba(89,191,255,.28)}
.decision-flow i{position:relative;width:24px;height:1px;background:linear-gradient(90deg,var(--sc-accent-deep),var(--sc-accent));box-shadow:0 0 7px rgba(42,201,255,.6)}
.decision-flow i::after{content:'';position:absolute;right:-1px;top:-3px;border-left:5px solid var(--sc-accent);border-top:3px solid transparent;border-bottom:3px solid transparent}
.decision-flow i::before{content:'';position:absolute;left:0;top:-1px;width:7px;height:3px;border-radius:2px;background:var(--sc-ink);box-shadow:0 0 8px var(--sc-ink);animation:flow-run 2.4s linear infinite}
.decision-flow i:nth-of-type(2)::before{animation-delay:-.8s}.decision-flow i:nth-of-type(3)::before{animation-delay:-1.6s}

@keyframes node-blink{0%,100%{opacity:1}50%{opacity:.45}}
@keyframes planetary-orbit{from{offset-distance:0%}to{offset-distance:100%}}
@keyframes flow-run{0%{left:0;opacity:0}18%,82%{opacity:1}100%{left:100%;opacity:0}}
@keyframes lane-cycle{to{stroke-dashoffset:-96}}
@keyframes node-float{0%,100%{margin-top:0}50%{margin-top:-3px}}
@media(prefers-reduced-motion:reduce){.cap-node,.core-orb b i,.decision-flow i::before,.capability,.lane-flow,.shield-stand{animation:none}.lane-runner{display:none}}
@media(max-width:900px){
  .core-stage-frame{--node-w:168px}
  .capability small{display:none}
  .capability{min-height:58px;offset-path:ellipse(35% 29% at 50% 46%)}
  .cap-orbit-body{min-height:58px;gap:8px;padding:6px 8px}
  .cap-icon{flex-basis:46px;width:46px;height:46px}
  .cap-icon :deep(svg){width:22px;height:22px}
  .core-3d{left:0;width:100%}
}
</style>
