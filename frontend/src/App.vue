<template>
  <div class="layout" :style="sidebarStyle">
    <aside class="sidebar" :class="{ collapsed: !sidebarOpen }">
      <div class="brand">
        <div class="brand-mark"><ShieldIcon :size="20" /></div>
        <div v-show="sidebarOpen" class="brand-copy">
          <strong>{{ PLATFORM_NAME }}</strong>
        </div>
      </div>

      <nav class="nav" aria-label="主导航">
        <router-link v-for="item in navItems" :key="item.to" :to="item.to"
          class="nav-item" active-class="nav-active" :title="item.label">
          <component :is="item.icon" class="nav-icon" :size="18" />
          <span v-show="sidebarOpen">{{ item.label }}</span>
        </router-link>
      </nav>

      <SidebarAccount :expanded="sidebarOpen" />

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
          <strong>{{ currentTitle }}</strong>
        </div>
        <div class="top-status"><i></i><span>实时防护已启用</span></div>
      </header>
      <div class="content"><router-view /></div>
    </main>

    <div v-if="showAbout" class="about-mask" @click.self="showAbout=false">
      <div class="about-dialog" role="dialog" aria-modal="true" aria-label="关于系统">
        <div class="about-header"><ShieldIcon :size="20" /><strong>{{ PLATFORM_NAME }}</strong><button class="icon-command" title="关闭" @click="showAbout=false">×</button></div>
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
import SidebarAccount from './components/auth/SidebarAccount.vue'
import { restoreSession } from './composables/useAuth'
import {
  BookOpen as BookIcon,
  ChartNoAxesCombined as ChartIcon,
  Image as ImageIcon,
  Info as InfoIcon,
  Menu as MenuIcon,
  PanelLeftClose as MenuOpenIcon,
  Radar as RadarIcon,
  Settings as SettingsIcon,
  ShieldCheck as ShieldIcon,
} from 'lucide-vue-next'

const navItems = [
  { to: '/detect', icon: ImageIcon, label: '图片与人脸审核' },
  { to: '/guardrail', icon: ShieldIcon, label: '实时安全护栏' },
  { to: '/scan', icon: RadarIcon, label: '主动安全扫描' },
  { to: '/kb', icon: BookIcon, label: '红线知识库' },
  { to: '/rag', icon: BookIcon, label: '红线策略' },
  { to: '/report', icon: ChartIcon, label: '审计与取证' },
  { to: '/settings', icon: SettingsIcon, label: '系统设置' },
]
const PLATFORM_NAME = '面向 AIGC 伪造的跨域泛化检测与可解释性防御平台'
const route = useRoute()
const sidebarOpen = ref(window.innerWidth > 760)
const showAbout = ref(false)
const currentTitle = computed(() => navItems.find(n => route.path.startsWith(n.to))?.label ?? PLATFORM_NAME)
const sidebarStyle = computed(() => ({ '--sidebar-w': sidebarOpen.value ? '252px' : '68px' }))
const onResize = () => { if (window.innerWidth <= 760) sidebarOpen.value = false }
onMounted(() => {
  window.addEventListener('resize', onResize)
  restoreSession()
})
onBeforeUnmount(() => window.removeEventListener('resize', onResize))
watch(currentTitle, (title) => { document.title = `${title} - ${PLATFORM_NAME}` }, { immediate: true })
watch(() => route.path, () => { if (window.innerWidth <= 760) sidebarOpen.value = false })
</script>

<style>
:root {
  color-scheme: light;
  --bg: #f2f5f8; --surface: #ffffff; --surface-2: #f7f9fb; --surface-3: #eaf1f6;
  --line: #d9e2ea; --line-bright: #b7c6d3; --text: #172838; --muted: #5d7082;
  --faint: #8494a3; --primary: #087eae; --primary-strong: #066b96; --cyan: #168ca8;
  --warning: #b86f12; --danger: #cf3f4f; --success: #16805e;
  --sidebar: #10283c; --sidebar-2: #17364e; --sidebar-line: #29485e;
  --shadow-sm: 0 1px 2px rgba(23,40,56,.05), 0 5px 16px rgba(23,40,56,.04);
  --shadow-md: 0 12px 34px rgba(23,40,56,.08);
}
*, *::before, *::after { box-sizing: border-box; }
html, body, #app { min-height: 100%; margin: 0; }
body { font-family: Inter, 'PingFang SC', 'Microsoft YaHei', sans-serif; background: var(--bg); color: var(--text); letter-spacing: 0; }
button, input, textarea, select { font: inherit; }
button:focus-visible, a:focus-visible, input:focus-visible, textarea:focus-visible, select:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px; }
.layout { display:flex; min-height:100vh; background-color:var(--bg); background-image:linear-gradient(rgba(23,40,56,.026) 1px,transparent 1px),linear-gradient(90deg,rgba(23,40,56,.026) 1px,transparent 1px); background-size:28px 28px; }
.sidebar { width:var(--sidebar-w); min-width:var(--sidebar-w); height:100vh; position:sticky; top:0; z-index:50; display:flex; flex-direction:column; padding:14px 10px; background:var(--sidebar); border-right:1px solid var(--sidebar-line); box-shadow:8px 0 28px rgba(16,40,60,.08); transition:width .22s ease,min-width .22s ease; overflow:hidden; }
.brand { min-height:104px; display:flex; align-items:center; gap:11px; padding:10px 8px 14px; border-bottom:1px solid var(--sidebar-line); }
.brand-mark { width:38px; height:38px; flex:0 0 38px; display:grid; place-items:center; color:#ffffff; background:var(--primary); border-radius:6px; box-shadow:0 8px 20px rgba(0,0,0,.16); }
.brand-copy { min-width:0; width:179px; }
.brand-copy strong { display:block; color:#f5f9fc; font-size:13px; line-height:1.5; font-weight:750; white-space:normal; overflow-wrap:anywhere; }
.nav { flex:1; padding:14px 0; display:flex; flex-direction:column; gap:4px; overflow-y:auto; }
.nav-item { min-height:42px; display:flex; align-items:center; gap:11px; padding:0 14px; border:1px solid transparent; border-radius:6px; color:#b5c6d2; text-decoration:none; font-size:13px; white-space:nowrap; transition:background .16s,color .16s,border-color .16s; }
.nav-item:hover { color:#ffffff; background:var(--sidebar-2); border-color:var(--sidebar-line); }
.nav-active { color:#ffffff !important; background:rgba(8,126,174,.36) !important; border-color:rgba(70,183,224,.34) !important; box-shadow:inset 3px 0 #6fd2e8; font-weight:650; }
.nav-icon { flex:0 0 auto; }
.sidebar-foot { height:52px; display:flex; align-items:center; gap:8px; border-top:1px solid var(--sidebar-line); padding:10px 4px 0; }
.engine-state { flex:1; min-width:0; display:flex; align-items:center; gap:7px; font-size:11px; color:#a9bdcb; white-space:nowrap; }
.engine-state i,.top-status i { width:7px; height:7px; background:var(--success); border-radius:50%; box-shadow:0 0 9px rgba(52,211,153,.65); }
.engine-state b { margin-left:auto; color:#8299aa; font:10px ui-monospace,monospace; }
.main { min-width:0; flex:1; display:flex; flex-direction:column; height:100vh; overflow:hidden; }
.topbar { height:58px; flex:0 0 58px; display:flex; align-items:center; gap:12px; padding:0 22px; border-bottom:1px solid var(--line); background:rgba(255,255,255,.94); backdrop-filter:blur(14px); box-shadow:var(--shadow-sm); z-index:30; }
.icon-command { width:34px; height:34px; flex:0 0 34px; display:grid; place-items:center; color:var(--muted); background:#ffffff; border:1px solid var(--line); border-radius:6px; cursor:pointer; }
.icon-command:hover { color:var(--primary); border-color:var(--line-bright); background:var(--surface-3); }
.sidebar .icon-command { color:#b5c6d2; background:transparent; border-color:var(--sidebar-line); }
.sidebar .icon-command:hover { color:#ffffff; background:var(--sidebar-2); }
.breadcrumb { display:flex; align-items:center; gap:9px; font-size:12px; color:var(--faint); }
.breadcrumb i { font-style:normal; }.breadcrumb strong { color:var(--text); font-size:13px; }
.top-status { margin-left:auto; display:flex; align-items:center; gap:8px; color:var(--muted); font-size:11px; }
.content { flex:1; min-height:0; overflow:auto; padding:22px 26px 40px; }
.card { background:var(--surface); border:1px solid var(--line); border-radius:8px; padding:18px 20px; box-shadow:var(--shadow-sm); }
.card:hover { border-color:#c7d4df; box-shadow:var(--shadow-md); }
.card-title { display:flex; align-items:center; gap:9px; margin-bottom:14px; color:var(--text); font-size:13px; font-weight:650; }
.card-title::before { content:''; width:3px; height:14px; background:var(--primary); border-radius:1px; }
.about-mask { position:fixed; inset:0; z-index:200; display:grid; place-items:center; padding:20px; background:rgba(16,40,60,.42); backdrop-filter:blur(5px); }
.about-dialog { width:min(470px,100%); padding:22px; background:var(--surface); border:1px solid var(--line-bright); border-radius:8px; box-shadow:0 24px 80px rgba(16,40,60,.26); }
.about-header { display:flex; align-items:center; gap:10px; padding-bottom:14px; border-bottom:1px solid var(--line); color:var(--primary); }.about-header .icon-command { margin-left:auto; }
.about-body { padding-top:8px; }.about-row { display:grid; grid-template-columns:100px 1fr; gap:12px; padding:11px 0; border-bottom:1px solid var(--line); font-size:12px; }.about-row span { color:var(--muted); }.about-row b { font-weight:500; color:var(--text); }
.mobile-mask { display:none; }

/* Shared controls and status tokens */
.badge { border-radius:4px !important; }.badge-success { background:rgba(22,128,94,.11) !important; color:var(--success) !important; }.badge-danger { background:rgba(207,63,79,.1) !important; color:var(--danger) !important; }.badge-warn { background:rgba(184,111,18,.11) !important; color:var(--warning) !important; }
.el-upload-dragger,.el-input__wrapper,.el-textarea__inner { background:var(--surface-2) !important; border-color:var(--line) !important; box-shadow:none !important; color:var(--text) !important; }
.el-upload-dragger:hover { border-color:var(--primary) !important; }
:root { --el-color-primary:var(--primary); --el-bg-color:var(--surface); --el-fill-color-blank:var(--surface); --el-text-color-primary:var(--text); --el-text-color-regular:var(--muted); --el-border-color:var(--line); }

@media (max-width: 900px) { .content { padding:18px; } }
@media (max-width: 760px) {
  .sidebar { position:fixed; left:0; top:0; width:252px; min-width:252px; transform:translateX(0); transition:transform .2s ease; }
  .sidebar.collapsed { transform:translateX(-100%); }
  .mobile-mask { display:block; position:fixed; inset:0; z-index:40; border:0; background:rgba(16,40,60,.45); }
  .topbar { padding:0 14px; }.top-status span { display:none; }.content { padding:14px; }
}
</style>
