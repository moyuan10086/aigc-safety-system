<template>
  <section class="screen-panel">
    <header class="panel-title">
      <strong>{{ title }}</strong>
      <span>{{ code }}</span>
    </header>
    <slot />
  </section>
</template>

<script setup lang="ts">
defineProps<{ title: string; code: string }>()
</script>

<style scoped>
/* The root paints only the 1px edge ring: a flat edge colour across the whole clipped
   shape, plus an accent square at the TL/BR cuts so those diagonals read as lit bevels.
   Painting the ring here (rather than with `border`) is what keeps the diagonal edges
   visible -- clip-path slices a real border away along the cuts. */
.screen-panel{--cut-tl:12px;--cut-tr:22px;--cut-br:12px;--cut-bl:18px;position:relative;min-width:0;min-height:0;box-sizing:border-box;isolation:isolate;overflow:hidden;background-color:rgba(61,143,180,.6);background-image:linear-gradient(rgba(72,216,233,.85),rgba(72,216,233,.85)),linear-gradient(rgba(72,216,233,.85),rgba(72,216,233,.85));background-size:calc(var(--cut-tl) + 2px) calc(var(--cut-tl) + 2px),calc(var(--cut-br) + 2px) calc(var(--cut-br) + 2px);background-position:0 0,100% 100%;background-repeat:no-repeat;clip-path:polygon(0 var(--cut-tl),var(--cut-tl) 0,calc(100% - var(--cut-tr)) 0,100% var(--cut-tr),100% calc(100% - var(--cut-br)),calc(100% - var(--cut-br)) 100%,var(--cut-bl) 100%,0 calc(100% - var(--cut-bl)))}
.screen-panel :deep(*){box-sizing:border-box}
/* Translucent layered surface + subtle technical grid, inset 1px to reveal the ring.
   z-index:-1 sits above the root background but below slot content; `isolation` on the
   root scopes that negative layer so it cannot fall behind the page. */
.screen-panel::before{content:'';position:absolute;inset:1px;z-index:-1;pointer-events:none;background-color:rgba(6,25,39,.9);background-image:radial-gradient(115% 80% at 0 0,rgba(49,198,220,.1),transparent 60%),linear-gradient(138deg,rgba(24,74,104,.55),rgba(4,20,33,0) 46%),linear-gradient(rgba(88,182,218,.05) 1px,transparent 1px),linear-gradient(90deg,rgba(88,182,218,.05) 1px,transparent 1px);background-size:auto,auto,16px 16px,16px 16px;clip-path:polygon(0 calc(var(--cut-tl) - 1px),calc(var(--cut-tl) - 1px) 0,calc(100% - var(--cut-tr) + 1px) 0,100% calc(var(--cut-tr) - 1px),100% calc(100% - var(--cut-br) + 1px),calc(100% - var(--cut-br) + 1px) 100%,calc(var(--cut-bl) - 1px) 100%,0 calc(100% - var(--cut-bl) + 1px))}
/* Active scan edge: a highlight sweeping the top edge, between the two corner cuts. */
.screen-panel::after{content:'';position:absolute;top:1px;left:var(--cut-tl);right:var(--cut-tr);height:2px;z-index:3;pointer-events:none;background-image:linear-gradient(90deg,transparent,rgba(65,204,228,.25) 22%,#6fe6f6 50%,rgba(65,204,228,.25) 78%,transparent);background-size:42% 100%;background-repeat:no-repeat;background-position:-60% 0;animation:panel-scan 5.6s linear infinite}
@keyframes panel-scan{to{background-position:160% 0}}
/* Right padding clears the top-right diagonal cut, which eats up to --cut-tr of width
   at the very top of the 34px header. Height stays 34px: sibling views size slot
   content with calc(100% - 34px). */
.panel-title{position:relative;height:34px;display:flex;align-items:center;padding:0 15px 0 12px;border-bottom:1px solid rgba(58,125,158,.55);background:linear-gradient(90deg,rgba(18,69,94,.22),transparent 65%)}
.panel-title::before{content:'';flex:none;width:5px;height:12px;margin-right:7px;background:#48d8e9;box-shadow:0 0 10px rgba(72,216,233,.75);clip-path:polygon(0 0,100% 20%,100% 80%,0 100%)}
.panel-title strong{min-width:0;overflow:hidden;font-family:"HarmonyOS Sans SC","Noto Sans SC","Source Han Sans SC","Microsoft YaHei",sans-serif;font-size:13px;font-weight:650;color:#edfaff;letter-spacing:0;white-space:nowrap;text-overflow:ellipsis}
/* Long codes (e.g. "CURATED BENCHMARK · SANITIZED") ellipsize instead of pushing the
   title out of the panel. #8fb8cc measures ~5:1 against the lightest part of the header
   gradient -- this text is 7px, so it needs the 4.5:1 normal-text threshold. */
.panel-title span{flex:0 1 auto;min-width:0;margin-left:auto;padding-left:8px;overflow:hidden;color:#8fb8cc;font:8px/1 ui-monospace,monospace;letter-spacing:0;white-space:nowrap;text-overflow:ellipsis}
@media(prefers-reduced-motion:reduce){.screen-panel::after{animation:none;background-size:100% 100%;background-position:0 0;background-image:linear-gradient(90deg,rgba(65,204,228,.6),rgba(65,204,228,.08) 76%,transparent)}}
</style>
