<template>
  <div class="settings-page">
    <section class="page-head">
      <div>
        <div class="eyebrow">RUNTIME POSTURE</div>
        <h1>系统运行状态</h1>
        <p>演示环境采用服务端托管配置，模型密钥、服务地址与本地路径不会暴露到浏览器。</p>
      </div>
      <div class="managed-badge"><LockKeyhole :size="14" />配置已锁定</div>
    </section>

    <section class="status-grid">
      <article v-for="item in statusItems" :key="item.label" class="status-card">
        <div class="status-icon"><component :is="item.icon" :size="19" /></div>
        <div>
          <span>{{ item.label }}</span>
          <b>{{ item.value }}</b>
        </div>
        <i :class="item.ready ? 'online' : 'offline'"></i>
      </article>
    </section>

    <section class="card deployment-card">
      <div class="card-title">部署信息</div>
      <div class="info-rows">
        <div><span>系统名称</span><b>面向 AIGC 伪造的跨域泛化检测与可解释性防御平台</b></div>
        <div><span>生成模型</span><b>{{ info.chat_model || '未配置' }}</b></div>
        <div><span>多模态模型</span><b>{{ info.mllm_model || '未配置' }}</b></div>
        <div><span>护栏架构</span><b>输入预检 / 模型执行 / 输出复检</b></div>
        <div><span>服务框架</span><b>FastAPI + Vue 3</b></div>
        <div><span>配置方式</span><b>服务器环境变量</b></div>
      </div>
    </section>

    <section class="security-note">
      <ShieldCheck :size="18" />
      <div><b>生产保护已启用</b><p>浏览器端只读取可公开的运行状态。敏感配置修改接口默认关闭，跨域来源限制为部署域名和本地开发环境。</p></div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive } from 'vue'
import { Bot, Database, Eye, LockKeyhole, ScanFace, ShieldCheck } from 'lucide-vue-next'
import { toast } from 'vue3-toastify'

const info = reactive<any>({})

const statusItems = computed(() => [
  { label:'安全对话模型', value:info.chat_model || '未配置', ready:!!info.chat_model_configured, icon:Bot },
  { label:'多模态审核', value:info.mllm_model || '未配置', ready:!!info.mllm_configured, icon:Eye },
  { label:'人脸伪造检测', value:info.deepfake_configured ? '模型路径已就绪' : '待配置', ready:!!info.deepfake_configured, icon:ScanFace },
  { label:'红线知识库', value:info.rag_configured ? '检索引擎已就绪' : '待配置', ready:!!info.rag_configured, icon:Database },
])

onMounted(async () => {
  try {
    const response = await fetch('/api/system/info')
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    Object.assign(info, await response.json())
  } catch {
    toast.error('无法读取系统运行状态')
  }
})
</script>

<style scoped>
.settings-page{max-width:1050px;margin:0 auto;display:flex;flex-direction:column;gap:18px}.page-head{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;padding:4px 2px}.eyebrow{color:var(--primary);font:10px ui-monospace,monospace}.page-head h1{margin:7px 0;font-size:24px;letter-spacing:0}.page-head p{max-width:700px;margin:0;color:var(--muted);font-size:13px;line-height:1.7}.managed-badge{display:flex;align-items:center;gap:7px;padding:8px 11px;color:var(--primary);border:1px solid rgba(45,212,191,.22);border-radius:5px;background:rgba(45,212,191,.06);font-size:11px;white-space:nowrap}.status-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.status-card{position:relative;display:flex;align-items:center;gap:12px;min-width:0;padding:15px;border:1px solid var(--line);border-radius:7px;background:var(--surface-2)}.status-icon{display:grid;place-items:center;width:38px;height:38px;flex:0 0 38px;color:var(--primary);border:1px solid rgba(45,212,191,.18);border-radius:5px;background:rgba(45,212,191,.05)}.status-card span{display:block;margin-bottom:4px;color:var(--faint);font-size:9px}.status-card b{display:block;max-width:320px;overflow:hidden;color:var(--text);font-size:12px;font-weight:500;text-overflow:ellipsis;white-space:nowrap}.status-card>i{position:absolute;top:13px;right:13px;width:6px;height:6px;border-radius:50%}.status-card>i.online{background:var(--success);box-shadow:0 0 8px rgba(52,211,153,.6)}.status-card>i.offline{background:var(--warning)}.deployment-card{padding:18px}.info-rows{margin-top:12px}.info-rows div{display:grid;grid-template-columns:145px minmax(0,1fr);gap:15px;padding:11px 2px;border-bottom:1px solid var(--line)}.info-rows div:last-child{border-bottom:0}.info-rows span{color:var(--faint);font-size:11px}.info-rows b{color:var(--text);font-size:12px;font-weight:500;word-break:break-word}.security-note{display:flex;align-items:flex-start;gap:11px;padding:14px 16px;color:var(--success);border:1px solid rgba(52,211,153,.2);border-radius:7px;background:rgba(52,211,153,.05)}.security-note svg{flex:0 0 auto}.security-note b{font-size:11px}.security-note p{margin:5px 0 0;color:var(--muted);font-size:11px;line-height:1.6}@media(max-width:720px){.page-head{align-items:flex-start;flex-direction:column}.status-grid{grid-template-columns:1fr}.info-rows div{grid-template-columns:1fr;gap:5px}.page-head h1{font-size:20px}}
</style>
