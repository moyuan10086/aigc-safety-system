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
.screen-panel{position:relative;min-width:0;min-height:0;box-sizing:border-box;background:rgba(8,31,47,.94);border:1px solid #1d4862;overflow:hidden}
.screen-panel :deep(*){box-sizing:border-box}
.screen-panel::before,.screen-panel::after{content:'';position:absolute;width:12px;height:12px;border-color:#31c6dc;z-index:3;pointer-events:none}
.screen-panel::before{left:-1px;top:-1px;border-left:2px solid;border-top:2px solid}
.screen-panel::after{right:-1px;bottom:-1px;border-right:2px solid;border-bottom:2px solid}
.panel-title{height:34px;display:flex;align-items:center;padding:0 10px;border-bottom:1px solid rgba(43,94,122,.65)}
.panel-title strong{font-size:10px;color:#d8eef7}
.panel-title span{margin-left:auto;color:#49758c;font:7px ui-monospace,monospace}
</style>
