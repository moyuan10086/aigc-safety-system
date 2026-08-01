<template>
  <div class="layout" :style="sidebarStyle">
    <aside class="sidebar" :class="{ collapsed: !sidebarOpen }">
      <div class="brand">
        <div class="brand-mark"><ShieldIcon :size="20" /></div>
        <div v-show="sidebarOpen" class="brand-copy">
          <strong>AIGC 安全运营台</strong>
          <span>CONTENT REVIEW &amp; GUARDRAIL</span>
        </div>
      </div>

      <nav class="nav" aria-label="主导航">
        <router-link v-for="item in navItems" :key="item.to" :to="item.to"
          class="nav-item" active-class="nav-active" :title="item.label">
          <component :is="item.icon" class="nav-icon" :size="18" />
          <span v-show="sidebarOpen">{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="sidebar-foot">
        <div v-show="sidebarOpen" class="engine-state"><i></i><span>防护引擎在线</span><b>v1.1</b></div>
        <button class="icon-command" title="关于系统" @click="showAbout = true"><InfoIcon :size="18" /></button>
      </div>
    </aside>

    <button v-if="sidebarOpen" class="mobile-mask" aria-label="关闭导航" @click="sidebarOpen=false"></button>

    <main class="main">
      <header class="topbar">
        <button class="icon-command" :title="sidebarOpen ? '收起导航' : '展开导航'" @click="sidebarOpen = !sidebarOpen">
          <MenuOpenIcon v-if="sidebarOpen" :size="21" /><MenuIcon v-else :size="21" />
        </button>
        <div class="breadcrumb">
          <span>安全运营中心</span><i>/</i><strong>{{ currentTitle }}</strong>
        </div>
        <div class="top-status"><i></i><span>实时防护已启用</span></div>
      </header>
      <div class="content"><router-view /></div>
    </main>

    <div v-if="showAbout" class="about-mask" @click.self="showAbout=false">
      <div class="about-dialog" role="dialog" aria-modal="true" aria-label="关于系统">
        <div class="about-header"><ShieldIcon :size="20" /><strong>AIGC 安全运营台</strong><button class="icon-command" title="关闭" @click="showAbout=false">×</button></div>
        <div class="about-body">
          <div class="about-row"><span>系统定位</span><b>多模态内容审核与大模型安全护栏</b></div>
          <div class="about-row"><span>核心能力</span><b>伪造检测 / 红线审核 / 输入输出防护</b></div>
          <div class="about-row"><span>检测模型</span><b>CLIP ViT-L/14 + MLLM</b></div>
          <div class="about-row"><span>知识引擎</span><b>ChromaDB + SentenceTransformers</b></div>
          <div class="about-row"><span>版本</span><b>Competition Demo 1.1</b></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

const icon = (body: string) => ({ template: `<svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`, props: ['size'] })
const ImageIcon = icon('<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/>')
const ShieldIcon = icon('<path d="M20 13c0 5-3.5 7.5-8 9-4.5-1.5-8-4-8-9V5l8-3 8 3v8z"/><path d="m9 12 2 2 4-4"/>')
const RadarIcon = icon('<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3"/><path d="M12 3v3m0 12v3M3 12h3m12 0h3"/>')
const BookIcon = icon('<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5V4.5A2.5 2.5 0 0 1 6.5 2z"/>')
const ChartIcon = icon('<path d="M3 3v18h18"/><path d="m7 16 4-5 3 3 5-7"/>')
const SettingsIcon = icon('<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06A1.7 1.7 0 0 0 15 19.4V21h-4v-.09A1.7 1.7 0 0 0 9 19.4l-1.88.34-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.6 15H3v-4h.09A1.7 1.7 0 0 0 4.6 9L4.26 7.1l2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.6V3h4v.09A1.7 1.7 0 0 0 15 4.6l1.88-.34 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.4 9H21v4h-.09A1.7 1.7 0 0 0 19.4 15z"/>')
const InfoIcon = icon('<circle cx="12" cy="12" r="10"/><path d="M12 16v-4m0-4h.01"/>')
const MenuIcon = icon('<path d="M4 6h16M4 12h16M4 18h16"/>')
const MenuOpenIcon = icon('<path d="M4 6h16M4 12h10M4 18h16"/>')

const navItems = [
  { to: '/detect', icon: ImageIcon, label: '图片与人脸审核' },
  { to: '/guardrail', icon: ShieldIcon, label: '实时安全护栏' },
  { to: '/scan', icon: RadarIcon, label: '主动安全扫描' },
  { to: '/kb', icon: BookIcon, label: '红线知识库' },
  { to: '/rag', icon: BookIcon, label: '红线策略' },
  { to: '/report', icon: ChartIcon, label: '审计与取证' },
  { to: '/settings', icon: SettingsIcon, label: '系统设置' },
]
const route = useRoute()
const sidebarOpen = ref(window.innerWidth > 760)
const showAbout = ref(false)
const currentTitle = computed(() => navItems.find(n => route.path.startsWith(n.to))?.label ?? '安全运营中心')
const sidebarStyle = computed(() => ({ '--sidebar-w': sidebarOpen.value ? '236px' : '68px' }))
const onResize = () => { if (window.innerWidth <= 760) sidebarOpen.value = false }
onMounted(() => window.addEventListener('resize', onResize))
onBeforeUnmount(() => window.removeEventListener('resize', onResize))
watch(() => route.path, () => { if (window.innerWidth <= 760) sidebarOpen.value = false })
</script>

<style>
:root {
  color-scheme: dark;
  --bg: #080d12; --surface: #101820; --surface-2: #131f28; --surface-3: #182630;
  --line: #263846; --line-bright: #355365; --text: #e8f0f7; --muted: #91a4b5;
  --faint: #607383; --primary: #2dd4bf; --primary-strong: #14b8a6; --cyan: #38bdf8;
  --warning: #f59e0b; --danger: #fb7185; --success: #34d399;
}
*, *::before, *::after { box-sizing: border-box; }
html, body, #app { min-height: 100%; margin: 0; }
body { font-family: Inter, 'PingFang SC', 'Microsoft YaHei', sans-serif; background: var(--bg); color: var(--text); letter-spacing: 0; }
button, input, textarea, select { font: inherit; }
button:focus-visible, a:focus-visible, input:focus-visible, textarea:focus-visible, select:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px; }
.layout { display:flex; min-height:100vh; background: radial-gradient(circle at 72% 0%, rgba(45,212,191,.06), transparent 28%), var(--bg); }
.sidebar { width:var(--sidebar-w); min-width:var(--sidebar-w); height:100vh; position:sticky; top:0; z-index:50; display:flex; flex-direction:column; padding:14px 10px; background:#0c1319; border-right:1px solid var(--line); transition:width .22s ease,min-width .22s ease; overflow:hidden; }
.brand { height:64px; display:flex; align-items:center; gap:11px; padding:8px; border-bottom:1px solid var(--line); }
.brand-mark { width:38px; height:38px; flex:0 0 38px; display:grid; place-items:center; color:#07110f; background:var(--primary); border-radius:6px; box-shadow:0 0 20px rgba(45,212,191,.18); }
.brand-copy { min-width:165px; display:flex; flex-direction:column; gap:4px; }
.brand-copy strong { font-size:14px; white-space:nowrap; }
.brand-copy span { font:8px/1.1 ui-monospace, SFMono-Regular, Consolas, monospace; color:var(--faint); }
.nav { flex:1; padding:14px 0; display:flex; flex-direction:column; gap:4px; overflow-y:auto; }
.nav-item { min-height:42px; display:flex; align-items:center; gap:11px; padding:0 14px; border:1px solid transparent; border-radius:6px; color:var(--muted); text-decoration:none; font-size:13px; white-space:nowrap; transition:background .16s,color .16s,border-color .16s; }
.nav-item:hover { color:var(--text); background:var(--surface); border-color:var(--line); }
.nav-active { color:var(--primary) !important; background:rgba(45,212,191,.08) !important; border-color:rgba(45,212,191,.2) !important; box-shadow:inset 3px 0 var(--primary); }
.nav-icon { flex:0 0 auto; }
.sidebar-foot { height:52px; display:flex; align-items:center; gap:8px; border-top:1px solid var(--line); padding:10px 4px 0; }
.engine-state { flex:1; min-width:0; display:flex; align-items:center; gap:7px; font-size:11px; color:var(--muted); white-space:nowrap; }
.engine-state i,.top-status i { width:7px; height:7px; background:var(--success); border-radius:50%; box-shadow:0 0 9px rgba(52,211,153,.65); }
.engine-state b { margin-left:auto; color:var(--faint); font:10px ui-monospace,monospace; }
.main { min-width:0; flex:1; display:flex; flex-direction:column; height:100vh; overflow:hidden; }
.topbar { height:58px; flex:0 0 58px; display:flex; align-items:center; gap:12px; padding:0 22px; border-bottom:1px solid var(--line); background:rgba(8,13,18,.9); backdrop-filter:blur(14px); z-index:30; }
.icon-command { width:34px; height:34px; flex:0 0 34px; display:grid; place-items:center; color:var(--muted); background:transparent; border:1px solid var(--line); border-radius:6px; cursor:pointer; }
.icon-command:hover { color:var(--primary); border-color:var(--line-bright); background:var(--surface-2); }
.breadcrumb { display:flex; align-items:center; gap:9px; font-size:12px; color:var(--faint); }
.breadcrumb i { font-style:normal; }.breadcrumb strong { color:var(--text); font-size:13px; }
.top-status { margin-left:auto; display:flex; align-items:center; gap:8px; color:var(--muted); font-size:11px; }
.content { flex:1; min-height:0; overflow:auto; padding:22px 26px 40px; }
.card { background:linear-gradient(145deg,rgba(19,31,40,.96),rgba(14,23,30,.96)); border:1px solid var(--line); border-radius:8px; padding:18px 20px; box-shadow:0 12px 30px rgba(0,0,0,.16); }
.card-title { display:flex; align-items:center; gap:9px; margin-bottom:14px; color:var(--text); font-size:13px; font-weight:650; }
.card-title::before { content:''; width:3px; height:14px; background:var(--primary); border-radius:1px; box-shadow:0 0 8px rgba(45,212,191,.35); }
.about-mask { position:fixed; inset:0; z-index:200; display:grid; place-items:center; padding:20px; background:rgba(2,6,9,.78); backdrop-filter:blur(5px); }
.about-dialog { width:min(470px,100%); padding:22px; background:var(--surface); border:1px solid var(--line-bright); border-radius:8px; box-shadow:0 24px 80px #000; }
.about-header { display:flex; align-items:center; gap:10px; padding-bottom:14px; border-bottom:1px solid var(--line); color:var(--primary); }.about-header .icon-command { margin-left:auto; }
.about-body { padding-top:8px; }.about-row { display:grid; grid-template-columns:100px 1fr; gap:12px; padding:11px 0; border-bottom:1px solid var(--line); font-size:12px; }.about-row span { color:var(--muted); }.about-row b { font-weight:500; color:var(--text); }
.mobile-mask { display:none; }

/* Shared controls and status tokens */
.badge { border-radius:4px !important; }.badge-success { background:rgba(52,211,153,.12) !important; color:var(--success) !important; }.badge-danger { background:rgba(251,113,133,.12) !important; color:var(--danger) !important; }.badge-warn { background:rgba(245,158,11,.13) !important; color:var(--warning) !important; }
.el-upload-dragger,.el-input__wrapper,.el-textarea__inner { background:var(--surface-2) !important; border-color:var(--line) !important; box-shadow:none !important; color:var(--text) !important; }
.el-upload-dragger:hover { border-color:var(--primary) !important; }

@media (max-width: 900px) { .content { padding:18px; } }
@media (max-width: 760px) {
  .sidebar { position:fixed; left:0; top:0; width:236px; min-width:236px; transform:translateX(0); transition:transform .2s ease; }
  .sidebar.collapsed { transform:translateX(-100%); }
  .mobile-mask { display:block; position:fixed; inset:0; z-index:40; border:0; background:rgba(0,0,0,.62); }
  .topbar { padding:0 14px; }.top-status span { display:none; }.content { padding:14px; }
}
</style>
