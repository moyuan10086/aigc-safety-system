<template>
  <section class="pipeline-stage" :class="{ 'is-alert': alert }" aria-label="安全审核中枢能力拓扑">
    <AiCoreCanvas class="core-energy" :intensity="intensity" :alert="alert" />
    <span class="stage-grid" aria-hidden="true"></span>

    <i v-for="item in capabilities" :key="`${item.code}-link`" class="cap-link" :class="item.position" aria-hidden="true"></i>

    <article class="core-shell">
      <span class="core-beam" aria-hidden="true"></span>
      <span class="core-shadow" aria-hidden="true"></span>
      <span class="core-base" aria-hidden="true"></span>
      <span class="core-belt" aria-hidden="true"></span>
      <section class="core-orb">
        <span class="orb-ring" aria-hidden="true"></span>
        <span class="shield-stand"><ShieldCheck :size="37" /></span>
        <strong>安全审核中枢</strong>
        <span class="orb-code">POLICY ORCHESTRATOR</span>
        <b :class="{ degraded: configured < total }"><i aria-hidden="true"></i>{{ configured }}/{{ total }} 引擎在线</b>
      </section>
    </article>

    <article v-for="item in capabilities" :key="item.code" class="capability" :class="item.position">
      <span class="cap-icon"><component :is="item.icon" :size="34" /></span>
      <section class="cap-copy">
        <strong>{{ item.label }}</strong>
        <span>{{ item.code }}</span>
        <small>{{ item.detail }}</small>
      </section>
      <i class="cap-node" aria-hidden="true"></i>
    </article>

    <nav class="decision-flow" aria-label="安全审核处置链路">
      <span>输入采集</span><i aria-hidden="true"></i>
      <span>多模态判定</span><i aria-hidden="true"></i>
      <span>策略融合</span><i aria-hidden="true"></i>
      <span class="terminal">放行 / 复核 / 阻断</span>
    </nav>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { BookOpenCheck, Boxes, BrainCircuit, ScanFace, ShieldAlert, ShieldCheck } from 'lucide-vue-next'
import AiCoreCanvas from './AiCoreCanvas.vue'

const props = withDefaults(defineProps<{
  configured: number
  total: number
  alert?: boolean
}>(), { alert: false })

const intensity = computed(() => {
  if (!props.total) return 0.35
  return 0.35 + (props.configured / props.total) * 0.6
})

const capabilities = [
  { label: 'Deepfake 检测', code: 'DEEPFAKE / MLLM', detail: '真实性检测链路', icon: BrainCircuit, position: 'top-left' },
  { label: 'MLLM 理解分析', code: 'POLICY / LLM', detail: '多模态语义策略', icon: ScanFace, position: 'top-right' },
  { label: '实时防护', code: 'AUDIT / GUARDRAIL', detail: '实时审计与拦截', icon: ShieldCheck, position: 'mid-left' },
  { label: 'RAG 内容审核', code: 'RAG / KNOWLEDGE', detail: '检索增强审核链路', icon: BookOpenCheck, position: 'mid-right' },
  { label: '风险处置', code: 'REVIEW / ESCALATION', detail: '人工复核与处置', icon: ShieldAlert, position: 'bottom-left' },
  { label: '样本与取证', code: 'C2PA / HASH', detail: '溯源证据索引', icon: Boxes, position: 'bottom-right' },
]
</script>

<style scoped>
.pipeline-stage{
  --cx:50%;--cy:45%;
  position:relative;flex:1;min-height:0;overflow:hidden;
  background:radial-gradient(ellipse 42% 38% at var(--cx) var(--cy),var(--sc-nebula),transparent 74%);
}
.core-energy{z-index:1}
.stage-grid{
  position:absolute;left:12%;right:12%;top:10%;bottom:13%;z-index:1;pointer-events:none;
  background:repeating-linear-gradient(0deg,transparent 0 31px,var(--sc-grid-major) 32px),repeating-linear-gradient(90deg,transparent 0 31px,var(--sc-grid-major) 32px);
  clip-path:polygon(50% 0,100% 50%,50% 100%,0 50%);opacity:.42;transform:scaleY(.72);
}

.core-shell{
  position:absolute;left:var(--cx);top:var(--cy);z-index:4;width:360px;height:286px;
  transform:translate(-50%,-50%);pointer-events:none;
}
.core-shadow,.core-base,.core-belt,.core-orb{position:absolute;left:50%;transform:translateX(-50%);border-radius:50%}
.core-beam{position:absolute;left:50%;top:-34px;width:2px;height:342px;transform:translateX(-50%);background:linear-gradient(180deg,transparent,rgba(42,150,255,.05) 12%,rgba(42,177,255,.55) 47%,rgba(42,150,255,.14) 70%,transparent);filter:blur(1px);opacity:.72}
.core-shadow{bottom:3px;width:330px;height:72px;background:rgba(0,0,0,.34);filter:blur(13px)}
.core-base{
  bottom:20px;width:340px;height:104px;border:1px solid var(--sc-line-hi);
  background:linear-gradient(180deg,rgba(18,86,156,.82),rgba(3,27,58,.98) 70%);
  box-shadow:var(--sc-glow-3),inset 0 -22px 30px rgba(0,0,0,.34);
}
.core-base::before,.core-base::after{content:'';position:absolute;left:5%;right:5%;border-radius:50%;border:1px solid var(--sc-line-2)}
.core-base::before{top:9px;height:70px;background:radial-gradient(ellipse,rgba(42,201,255,.12),transparent 70%)}
.core-base::after{left:-8%;right:-8%;top:48px;height:86px;border-color:var(--sc-line-soft)}
.core-belt{
  bottom:47px;width:304px;height:64px;border:1px solid var(--sc-line-2);
  background:repeating-linear-gradient(90deg,rgba(42,155,255,.78) 0 8px,rgba(8,48,94,.42) 8px 17px);
  box-shadow:0 0 20px rgba(42,150,255,.34),inset 0 8px 14px rgba(92,203,255,.18);opacity:.74;
}
.core-orb{
  top:10px;width:308px;height:222px;display:flex;flex-direction:column;align-items:center;justify-content:center;
  border:2px solid var(--sc-line-hi);text-align:center;
  background:radial-gradient(ellipse at 46% 34%,rgba(78,182,255,.92),rgba(13,75,132,.98) 42%,rgba(4,33,72,.99) 76%,rgba(2,18,43,.99));
  box-shadow:0 0 0 7px rgba(42,130,255,.09),0 0 34px rgba(38,158,255,.34),inset 0 18px 42px rgba(184,235,255,.20),inset 0 -24px 34px rgba(0,7,25,.62);
}
.core-orb::before{content:'';position:absolute;left:10%;right:10%;top:13%;height:34%;border-top:1px solid rgba(197,241,255,.38);border-radius:50%;background:linear-gradient(180deg,rgba(164,231,255,.16),transparent 62%);pointer-events:none}
.core-orb::after{content:'';position:absolute;left:18%;right:18%;bottom:12px;height:16px;border-radius:50%;background:rgba(31,151,255,.22);filter:blur(7px);pointer-events:none}
.pipeline-stage.is-alert .core-orb{border-color:rgba(255,67,99,.58);box-shadow:0 0 0 7px rgba(255,67,99,.06),inset 0 0 42px rgba(255,67,99,.12),0 0 42px rgba(255,67,99,.2)}
.orb-ring{position:absolute;inset:13px;border-radius:50%;border:1px dashed rgba(170,222,255,.34)}
.orb-ring::after{content:'';position:absolute;inset:10px;border-radius:50%;border:1px solid var(--sc-line-soft)}
.shield-stand{position:relative;width:66px;height:78px;display:grid;place-items:center;color:var(--sc-ink);clip-path:polygon(50% 0,92% 17%,86% 68%,50% 100%,14% 68%,8% 17%);background:linear-gradient(145deg,rgba(126,221,255,.92),rgba(26,126,232,.80) 42%,rgba(2,38,103,.95));filter:drop-shadow(0 0 11px rgba(42,151,255,.76));transform:perspective(210px) rotateX(8deg) rotateY(-4deg)}
.shield-stand::before{content:'';position:absolute;inset:2px;clip-path:inherit;background:linear-gradient(160deg,rgba(57,147,221,.72),rgba(4,47,111,.92) 65%,rgba(3,23,64,.98));box-shadow:inset 0 0 18px rgba(130,226,255,.28)}
.shield-stand::after{content:'';position:absolute;left:15%;right:15%;top:12%;height:2px;background:rgba(224,250,255,.72);box-shadow:0 0 14px rgba(102,210,255,.8)}
.shield-stand :deep(svg){position:relative;z-index:1;stroke-width:1.55;filter:drop-shadow(0 0 7px rgba(216,247,255,.8))}
.core-orb strong{position:relative;margin-top:10px;color:var(--sc-ink);font:700 20px var(--sc-font);text-shadow:0 0 14px rgba(42,201,255,.58)}
.orb-code{position:relative;margin-top:5px;color:var(--sc-ink-3);font:var(--sc-fs-code) var(--sc-font-mono);letter-spacing:var(--sc-ls-code)}
.core-orb b{position:relative;margin-top:10px;display:inline-flex;align-items:center;gap:7px;padding:4px 13px;border:1px solid rgba(60,232,170,.42);border-radius:18px;color:var(--sc-mint);background:var(--sc-mint-soft);font:600 var(--sc-fs-aux) var(--sc-font-num)}
.core-orb b i{width:6px;height:6px;border-radius:50%;background:currentColor;box-shadow:0 0 8px currentColor;animation:node-blink 2.4s ease-in-out infinite}
.core-orb b.degraded{color:var(--sc-medium);background:var(--sc-medium-soft);border-color:rgba(255,181,69,.44)}

.capability{
  position:absolute;z-index:5;width:224px;min-height:82px;display:flex;align-items:center;padding:10px 12px 10px 70px;
  border:1px solid var(--sc-line-soft);border-radius:4px;
  background:linear-gradient(100deg,rgba(7,47,73,.64),rgba(3,22,38,.74) 72%,rgba(3,18,31,.34));
  box-shadow:inset 0 0 18px rgba(42,201,255,.035);
}
.capability::before{content:'';position:absolute;left:69px;right:12px;top:38px;height:1px;background:linear-gradient(90deg,var(--sc-line-2),transparent)}
.cap-icon{
  position:absolute;left:-30px;top:50%;width:72px;height:72px;display:grid;place-items:center;transform:translateY(-50%);
  clip-path:polygon(50% 0,93% 24%,93% 76%,50% 100%,7% 76%,7% 24%);color:var(--sc-cyan);
  background:var(--sc-cyan);filter:drop-shadow(0 0 9px rgba(42,201,255,.38));
}
.cap-icon::before,.cap-icon::after{content:'';position:absolute;clip-path:inherit}
.cap-icon::before{inset:2px;background:linear-gradient(145deg,rgba(8,66,96,.98),rgba(3,24,42,.98))}
.cap-icon::after{inset:9px;background:linear-gradient(145deg,rgba(16,100,134,.43),rgba(3,25,44,.2));box-shadow:inset 0 0 0 1px var(--sc-line-hi)}
.cap-icon :deep(svg){position:relative;z-index:2;width:34px;height:34px;stroke-width:1.55;filter:drop-shadow(0 0 6px rgba(34,227,216,.66))}
.cap-copy{min-width:0;display:flex;flex-direction:column;align-items:flex-start;gap:4px}
.capability strong{color:var(--sc-ink);font:650 16px var(--sc-font);white-space:nowrap}
.capability .cap-copy>span{color:var(--sc-ink-2);font:var(--sc-fs-code) var(--sc-font-mono);letter-spacing:.08em;white-space:nowrap}
.capability small{color:var(--sc-ink-3);font-size:var(--sc-fs-code);line-height:1.2;white-space:nowrap}
.cap-node{position:absolute;top:50%;right:-15px;width:7px;height:7px;margin-top:-3px;border-radius:50%;background:var(--sc-cyan);box-shadow:0 0 10px var(--sc-cyan);animation:node-blink 2.6s ease-in-out infinite}
.top-left{left:10%;top:4%}.top-right{right:7%;top:4%}.mid-left{left:4.5%;top:37%}.mid-right{right:1%;top:37%}.bottom-left{left:9%;bottom:16%}.bottom-right{right:7%;bottom:16%}

.cap-link{position:absolute;z-index:2;height:1px;background:linear-gradient(90deg,transparent,var(--sc-cyan),rgba(42,201,255,.16));box-shadow:0 0 6px rgba(42,201,255,.3);transform-origin:0 50%;pointer-events:none}
.cap-link::after{content:'';position:absolute;right:-3px;top:-3px;width:7px;height:7px;border-radius:50%;background:var(--sc-ink);box-shadow:0 0 10px var(--sc-cyan)}
.cap-link.top-left{left:29%;top:16%;width:21%;transform:rotate(27deg)}
.cap-link.top-right{left:50%;top:27%;width:22%;transform:rotate(-27deg)}
.cap-link.mid-left{left:25%;top:45%;width:14%}.cap-link.mid-right{left:61%;top:45%;width:14%}
.cap-link.bottom-left{left:29%;top:73%;width:20%;transform:rotate(-28deg)}
.cap-link.bottom-right{left:51%;top:63%;width:21%;transform:rotate(28deg)}

.decision-flow{position:absolute;left:5%;right:5%;bottom:3%;z-index:6;display:flex;align-items:center;justify-content:center;gap:10px}
.decision-flow span{padding:7px 13px;border:1px solid var(--sc-line-2);border-radius:var(--sc-radius-sm);color:var(--sc-ink-2);background:rgba(8,36,58,.82);font:var(--sc-fs-aux) var(--sc-font);white-space:nowrap}
.decision-flow .terminal{color:var(--sc-ink);border-color:var(--sc-line-hi)}
.decision-flow i{position:relative;width:28px;height:1px;background:linear-gradient(90deg,var(--sc-accent-deep),var(--sc-accent));box-shadow:0 0 7px rgba(42,201,255,.6)}
.decision-flow i::after{content:'';position:absolute;right:-1px;top:-3px;border-left:5px solid var(--sc-accent);border-top:3px solid transparent;border-bottom:3px solid transparent}
.decision-flow i::before{content:'';position:absolute;left:0;top:-1px;width:7px;height:3px;border-radius:2px;background:var(--sc-ink);box-shadow:0 0 8px var(--sc-ink);animation:flow-run 2.4s linear infinite}
.decision-flow i:nth-of-type(2)::before{animation-delay:-.8s}.decision-flow i:nth-of-type(3)::before{animation-delay:-1.6s}

@keyframes node-blink{0%,100%{opacity:1}50%{opacity:.45}}
@keyframes flow-run{0%{left:0;opacity:0}18%,82%{opacity:1}100%{left:100%;opacity:0}}
@media(prefers-reduced-motion:reduce){.cap-node,.core-orb b i,.decision-flow i::before{animation:none}}
</style>
