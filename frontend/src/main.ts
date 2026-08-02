import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'virtual:uno.css'
import { createRouter, createWebHistory } from 'vue-router'
import { MotionPlugin } from '@vueuse/motion'
import Vue3Toastify, { type ToastContainerOptions } from 'vue3-toastify'
import 'vue3-toastify/dist/index.css'
import App from './App.vue'
import Detect from './views/Detect.vue'
import Report from './views/Report.vue'
import Rag from './views/Rag.vue'
import Settings from './views/Settings.vue'
import Scan from './views/Scan.vue'
import Kb from './views/Kb.vue'
import Guardrail from './views/Guardrail.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/detect' },
    { path: '/detect', component: Detect },
    { path: '/guardrail', component: Guardrail },
    { path: '/report', component: Report },
    { path: '/rag', component: Rag },
    { path: '/kb', component: Kb },
    { path: '/scan', component: Scan },
    { path: '/settings', component: Settings },
  ],
})

createApp(App)
  .use(ElementPlus)
  .use(router)
  .use(MotionPlugin)
  .use(Vue3Toastify, { autoClose: 3000, position: 'top-right', theme: 'light' } as ToastContainerOptions)
  .mount('#app')
