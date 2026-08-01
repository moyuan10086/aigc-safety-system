<template>
  <div class="layout" :style="sidebarStyle">
    <!-- 粒子背景 -->
    <vue-particles
      id="tsparticles"
      :options="particlesOptions"
      style="position:fixed;top:0;left:0;width:100%;height:100%;z-index:0;pointer-events:none"
    />
    <aside class="sidebar" :class="{ collapsed: !sidebarOpen }">
      <div class="sidebar-inner">
        <div class="brand">
          <div class="brand-bar"></div>
          <span class="brand-name" v-show="sidebarOpen">AIGC安全</span>
        </div>

        <nav class="nav">
          <router-link v-for="item in navItems" :key="item.to"
            :to="item.to" class="nav-item" active-class="nav-active">
            <component :is="item.icon" class="nav-icon" :size="18" />
            <span class="nav-label" v-show="sidebarOpen">{{ item.label }}</span>
          </router-link>
        </nav>

        <div class="sidebar-bottom" v-show="sidebarOpen">
          <button class="bottom-btn theme-btn" @click="toggleTheme">
            <SunIcon v-if="!isDark" :size="16" />
            <MoonIcon v-else :size="16" />
            <span>切换主题</span>
          </button>
          <button class="bottom-btn info-btn" @click="showAbout = true">
            <InfoIcon :size="16" />
            <span>关于系统</span>
          </button>
        </div>
      </div>
    </aside>

    <main class="main">
      <div class="topbar">
        <button class="menu-btn" @click="sidebarOpen = !sidebarOpen">
          <MenuOpenIcon v-if="sidebarOpen" :size="22" />
          <MenuIcon v-else :size="22" />
        </button>
        <div class="breadcrumb">{{ currentTitle }}</div>
      </div>
      <div class="content">
        <router-view />
      </div>
    </main>

    <!-- 关于系统 dialog -->
    <div v-if="showAbout" class="about-mask" @click.self="showAbout=false">
      <div class="about-dialog" v-motion :initial="{opacity:0,scale:0.9}" :enter="{opacity:1,scale:1,transition:{duration:250}}">
        <div class="about-header">
          <div class="brand-bar"></div>
          <span style="font-weight:700;font-size:16px">关于系统</span>
          <button @click="showAbout=false" style="margin-left:auto;background:none;border:none;cursor:pointer;color:#94a3b8;font-size:18px">×</button>
        </div>
        <div class="about-body">
          <div class="about-row"><span class="about-k">系统名称</span><span class="about-v">AIGC内容安全检测系统</span></div>
          <div class="about-row"><span class="about-k">版本</span><span class="about-v">1.0.0</span></div>
          <div class="about-row"><span class="about-k">Deepfake模型</span><span class="about-v">CLIP ViT-L/14 + LN-tuning</span></div>
          <div class="about-row"><span class="about-k">后端框架</span><span class="about-v">FastAPI + SSE</span></div>
          <div class="about-row"><span class="about-k">前端框架</span><span class="about-v">Vue 3 + TypeScript</span></div>
          <div class="about-row"><span class="about-k">RAG引擎</span><span class="about-v">ChromaDB + SentenceTransformers</span></div>
          <div class="about-row"><span class="about-k">OCR引擎</span><span class="about-v">PaddleOCR + pypdf</span></div>
          <div class="about-row"><span class="about-k">开发者</span><span class="about-v">陈昊 · 广东技术师范大学</span></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'

// Simple inline SVG icon components
const SearchIcon = { template: `<svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>`, props: ['size'] }
const ChartIcon = { template: `<svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>`, props: ['size'] }
const BookIcon = { template: `<svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>`, props: ['size'] }
const SettingsIcon = { template: `<svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`, props: ['size'] }
const SunIcon = { template: `<svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`, props: ['size'] }
const MoonIcon = { template: `<svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`, props: ['size'] }
const InfoIcon = { template: `<svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`, props: ['size'] }
const MenuIcon = { template: `<svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>`, props: ['size'] }
const MenuOpenIcon = { template: `<svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="15" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>`, props: ['size'] }
const ShieldIcon = { template: `<svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`, props: ['size'] }

const navItems = [
  { to: '/detect', icon: SearchIcon, label: '图像检测' },
  { to: '/report', icon: ChartIcon, label: '审计报告' },
  { to: '/kb', icon: BookIcon, label: '知识库' },
  { to: '/rag', icon: BookIcon, label: 'RAG审核' },
  { to: '/scan', icon: ShieldIcon, label: 'LLM扫描' },
  { to: '/settings', icon: SettingsIcon, label: '系统设置' },
]

const route = useRoute()
const sidebarOpen = ref(true)
const isDark = ref(false)
const showAbout = ref(false)

const particlesOptions = {
  background: { color: { value: 'transparent' } },
  fpsLimit: 60,
  particles: {
    number: { value: 40, density: { enable: true } },
    color: { value: '#f472b6' },
    opacity: { value: 0.15 },
    size: { value: { min: 1, max: 3 } },
    links: { enable: true, color: '#f472b6', opacity: 0.08, distance: 150 },
    move: { enable: true, speed: 0.6, outModes: 'bounce' },
  },
  detectRetina: true,
}

const currentTitle = computed(() => {
  const item = navItems.find(n => route.path.startsWith(n.to))
  return item?.label ?? ''
})

const sidebarStyle = computed(() => ({
  '--sidebar-w': sidebarOpen.value ? '220px' : '60px'
}))

const toggleTheme = () => {
  isDark.value = !isDark.value
  document.documentElement.classList.toggle('dark', isDark.value)
  document.documentElement.style.setProperty(
    '--bg-gradient',
    isDark.value
      ? 'linear-gradient(135deg, #1a0a1e 0%, #0f0a1a 50%, #0a0f1a 100%)'
      : 'linear-gradient(135deg, #fff5f9 0%, #fdf2ff 50%, #f0f4ff 100%)'
  )
}
</script>

<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  background: linear-gradient(135deg, #fff5f9 0%, #fdf2ff 50%, #f0f4ff 100%);
  min-height: 100vh;
  color: #1e293b;
}

.layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

/* Sidebar */
.sidebar {
  width: var(--sidebar-w, 220px);
  min-width: var(--sidebar-w, 220px);
  transition: width 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), min-width 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  background: rgba(255,255,255,0.7);
  backdrop-filter: blur(20px) saturate(1.5);
  border-right: 1px solid #fce7f3;
  box-shadow: 2px 0 16px rgba(244,114,182,0.07);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  z-index: 50;
}
.sidebar-inner {
  width: 220px;
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 16px 12px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 8px 20px;
  border-bottom: 1px solid #fce7f3;
  margin-bottom: 8px;
}
.brand-bar {
  width: 4px;
  height: 20px;
  background: #f472b6;
  border-radius: 9999px;
  flex-shrink: 0;
  box-shadow: 0 0 8px rgba(244,114,182,0.4);
}
.brand-name {
  font-size: 16px;
  font-weight: 700;
  color: #1e293b;
  white-space: nowrap;
}

.nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow-y: auto;
  padding: 4px 0;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  color: #64748b;
  text-decoration: none;
  font-size: 14px;
  transition: all 0.18s;
  cursor: pointer;
  white-space: nowrap;
}
.nav-item:hover { background: #fdf2f8; color: #f472b6; }
.nav-active { background: #fdf2f8; color: #f472b6; font-weight: 600; }
.nav-icon { flex-shrink: 0; }
.nav-label { overflow: hidden; }

.sidebar-bottom {
  border-top: 1px solid #fce7f3;
  padding-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.bottom-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 9px 12px;
  border-radius: 9999px;
  border: none;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s;
  white-space: nowrap;
}
.theme-btn { background: rgba(244,114,182,0.08); color: #f472b6; }
.theme-btn:hover { background: rgba(244,114,182,0.15); box-shadow: 0 2px 8px rgba(244,114,182,0.15); }
.info-btn { background: rgba(100,116,139,0.06); color: #64748b; }
.info-btn:hover { background: rgba(100,116,139,0.12); }

/* Main */
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.topbar {
  height: 44px;
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 10px 12px 0;
  padding: 0 12px;
  background: rgba(255,255,255,0.5);
  backdrop-filter: blur(16px);
  border-radius: 9999px;
  border: 1px solid rgba(244,114,182,0.15);
  box-shadow: 0 2px 8px rgba(244,114,182,0.06);
  position: sticky;
  top: 10px;
  z-index: 30;
}
.menu-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: #64748b;
  display: flex;
  align-items: center;
  padding: 4px;
  border-radius: 9999px;
  transition: all 0.18s;
}
.menu-btn:hover { background: #fdf2f8; color: #f472b6; }
.breadcrumb {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
}

.content {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px 32px;
}

/* Global card */
.card {
  background: rgba(255,255,255,0.8);
  backdrop-filter: blur(12px);
  border-radius: 16px;
  box-shadow: 0 2px 16px rgba(244,114,182,0.08);
  padding: 20px 24px;
  border: 1px solid #fce7f3;
}
.card-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
}
.card-title::before {
  content: '';
  width: 3px;
  height: 14px;
  background: #f472b6;
  border-radius: 9999px;
  display: inline-block;
}
.about-mask { position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.3);backdrop-filter:blur(4px);z-index:200;display:flex;align-items:center;justify-content:center }
.about-dialog { background:white;border-radius:16px;padding:24px;width:400px;box-shadow:0 20px 60px rgba(244,114,182,0.2) }
.about-header { display:flex;align-items:center;gap:10px;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid #fce7f3 }
.about-body { display:flex;flex-direction:column;gap:10px }
.about-row { display:flex;align-items:center;font-size:13px;padding:6px 0;border-bottom:1px solid #fdf2f8 }
.about-k { color:#94a3b8;width:120px;flex-shrink:0 }
.about-v { color:#1e293b;font-weight:500 }
</style>
