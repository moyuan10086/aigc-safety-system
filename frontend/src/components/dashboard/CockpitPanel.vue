<template>
  <section class="screen-panel" :class="[tone, { 'is-flush': flush, 'is-focus': focus }]">
    <span class="panel-edge" aria-hidden="true"></span>
    <header class="panel-title">
      <span class="title-mark" aria-hidden="true"></span>
      <strong>{{ title }}</strong>
      <slot name="meta" />
      <span class="title-code">{{ code }}</span>
    </header>
    <div class="panel-body"><slot /></div>
  </section>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  title: string
  code: string
  /** 语义色：驱动标题标记、边角高光与顶部扫描线 */
  tone?: 'blue' | 'cyan' | 'violet' | 'danger'
  /** 内容自行控制内边距（图表 / 图片墙） */
  flush?: boolean
  /** 视觉焦点面板：更强的边缘光与环境光 */
  focus?: boolean
}>(), { tone: 'blue', flush: false, focus: false })
</script>

<style scoped>
/* 面板 = 四层结构：外发光 → 描边 → 表层渐变 → 内容。
   用 border-radius 而非 clip-path，切角改由 ::before 的角标表达，
   这样描边不会被裁掉，圆角也能配合外发光形成"悬浮"体积感。 */
.screen-panel{
  --tone:var(--sc-accent);
  --tone-soft:var(--sc-accent-soft);
  position:relative;
  min-width:0;min-height:0;
  display:flex;flex-direction:column;
  box-sizing:border-box;
  overflow:hidden;
  border:1px solid var(--sc-line);
  border-radius:var(--sc-radius);
  background:
    /* 左上角环境光渗透，给面板一个光源方向 */
    radial-gradient(120% 90% at 0 0,var(--sc-panel-bleed),transparent 58%),
    /* 斜向表层渐变，让面板中部比边缘亮一档 */
    linear-gradient(146deg,var(--sc-panel-3),rgba(6,24,42,0) 52%),
    /* 技术网格 */
    linear-gradient(var(--sc-grid) 1px,transparent 1px),
    linear-gradient(90deg,var(--sc-grid) 1px,transparent 1px),
    var(--sc-panel);
  background-size:auto,auto,18px 18px,18px 18px,auto;
  box-shadow:var(--sc-inset),var(--sc-depth);
}
.screen-panel.cyan{--tone:var(--sc-cyan);--tone-soft:rgba(34,227,216,.11)}
.screen-panel.violet{--tone:var(--sc-violet);--tone-soft:rgba(143,125,255,.12)}
.screen-panel.danger{--tone:var(--sc-danger);--tone-soft:var(--sc-danger-soft)}
.screen-panel :deep(*){box-sizing:border-box}

/* 焦点面板：抬高一层，外发光更强 —— 中央 AI 中枢用它成为第一视觉中心 */
.screen-panel.is-focus{
  border-color:var(--sc-line-hi);
  box-shadow:var(--sc-inset),var(--sc-depth),0 0 0 1px rgba(42,201,255,.10),0 0 60px -12px rgba(42,201,255,.30);
}

/* 四角"卡尺"角标 + 顶边扫描光：科技感来自克制的边缘细节，而非满屏霓虹 */
.panel-edge{position:absolute;inset:0;z-index:2;pointer-events:none;border-radius:inherit}
.panel-edge::before{
  content:'';position:absolute;inset:0;border-radius:inherit;
  /* 只在四个角画短边，形成"取景框"效果 */
  background:
    linear-gradient(var(--tone),var(--tone)) 0 0/13px 1px no-repeat,
    linear-gradient(var(--tone),var(--tone)) 0 0/1px 13px no-repeat,
    linear-gradient(var(--tone),var(--tone)) 100% 0/13px 1px no-repeat,
    linear-gradient(var(--tone),var(--tone)) 100% 0/1px 13px no-repeat,
    linear-gradient(var(--tone),var(--tone)) 0 100%/13px 1px no-repeat,
    linear-gradient(var(--tone),var(--tone)) 0 100%/1px 13px no-repeat,
    linear-gradient(var(--tone),var(--tone)) 100% 100%/13px 1px no-repeat,
    linear-gradient(var(--tone),var(--tone)) 100% 100%/1px 13px no-repeat;
  opacity:.62;
}
.panel-edge::after{
  content:'';position:absolute;left:14px;right:14px;top:0;height:1px;
  background:linear-gradient(90deg,transparent,var(--tone) 46%,#eafcff 50%,var(--tone) 54%,transparent);
  background-size:44% 100%;background-repeat:no-repeat;background-position:-58% 0;
  filter:drop-shadow(0 0 5px var(--tone));
  animation:panel-scan var(--sc-sweep) linear infinite;
}
@keyframes panel-scan{to{background-position:158% 0}}

/* 标题：模块标题字号提到 --sc-fs-title，英文代号退到最弱一档，形成明确层级 */
.panel-title{
  position:relative;z-index:3;flex:none;
  height:38px;display:flex;align-items:center;gap:9px;
  padding:0 var(--sc-pad) 0 13px;
  border-bottom:1px solid var(--sc-line-soft);
  background:var(--sc-panel-head);
}
.title-mark{
  flex:none;width:4px;height:15px;border-radius:1px;
  background:linear-gradient(180deg,#eafcff,var(--tone));
  box-shadow:0 0 10px var(--tone);
}
.panel-title strong{
  min-width:0;overflow:hidden;
  color:var(--sc-ink);
  font-family:var(--sc-font);
  font-size:var(--sc-fs-title);
  font-weight:var(--sc-w-title);
  letter-spacing:.02em;
  white-space:nowrap;text-overflow:ellipsis;
}
.title-code{
  flex:0 1 auto;min-width:0;margin-left:auto;padding-left:10px;
  overflow:hidden;
  color:var(--sc-ink-4);
  font-family:var(--sc-font-mono);
  font-size:var(--sc-fs-code);
  letter-spacing:var(--sc-ls-code);
  white-space:nowrap;text-overflow:ellipsis;
}

/* 内容区自适应剩余高度：调用方不再需要 calc(100% - 34px) 补偿标题高度 */
.panel-body{
  position:relative;z-index:1;
  flex:1;min-height:0;min-width:0;
  display:flex;flex-direction:column;
  padding:11px 13px;
}
.screen-panel.is-flush .panel-body{padding:0}
@media(prefers-reduced-motion:reduce){
  .panel-edge::after{
    animation:none;background-size:100% 100%;background-position:0 0;
    background-image:linear-gradient(90deg,var(--tone),transparent 72%);opacity:.5;
  }
}

/* The cockpit uses structural lines instead of stacked card chrome. */
.screen-panel{
  border-color:var(--screen-line-soft);
  border-radius:var(--screen-radius);
  background:linear-gradient(145deg,rgba(9,32,52,.72),rgba(4,16,29,.78));
  box-shadow:var(--screen-shadow);
}
.screen-panel.is-focus{border-color:var(--screen-line-focus);box-shadow:var(--screen-shadow),0 0 34px -18px rgba(42,201,255,.6)}
.panel-edge::before{opacity:.32}.panel-edge::after{opacity:.35}
.panel-title{height:36px;padding-inline:var(--screen-panel-padding);background:linear-gradient(90deg,rgba(19,78,116,.28),transparent 72%);border-bottom-color:var(--screen-line-soft)}
.panel-title strong{font-size:var(--fs-screen-title)}
.panel-body{padding:var(--screen-panel-padding)}
.screen-panel.is-flush .panel-body{padding:0}
</style>
