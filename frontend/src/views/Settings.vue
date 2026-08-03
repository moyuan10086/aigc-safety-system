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

    <section class="card api-card">
      <div class="api-heading">
        <div>
          <div class="card-title"><KeyRound :size="16" />开放 API 与租户</div>
          <p>通过 API Key 调用 v1 接口；密钥按租户隔离，并执行作用域、分钟限流和每日配额。</p>
        </div>
        <div class="api-actions">
          <button class="icon-button" title="刷新 API Key" :disabled="keysLoading || !user" @click="loadKeys"><RefreshCw :size="16" /></button>
          <button class="command-button" :disabled="!user" @click="showCreate = !showCreate"><Plus :size="16" />签发密钥</button>
        </div>
      </div>

      <div v-if="!user" class="api-empty"><LockKeyhole :size="18" /><span>请先从左侧账户区域登录审核员账号。</span></div>

      <form v-else-if="showCreate" class="key-form" @submit.prevent="createKey">
        <label><span>租户标识</span><input v-model.trim="form.tenant_id" maxlength="80" placeholder="competition-demo" required /></label>
        <label><span>密钥名称</span><input v-model.trim="form.name" maxlength="120" placeholder="现场演示客户端" required /></label>
        <label><span>每分钟请求</span><input v-model.number="form.rate_limit_per_minute" type="number" min="1" max="600" required /></label>
        <label><span>每日配额</span><input v-model.number="form.daily_quota" type="number" min="1" max="100000" required /></label>
        <fieldset>
          <legend>授权能力</legend>
          <label v-for="scope in scopeOptions" :key="scope.value" class="scope-option">
            <input v-model="form.scopes" type="checkbox" :value="scope.value" />
            <span>{{ scope.label }}</span>
          </label>
        </fieldset>
        <div class="form-actions">
          <button type="button" class="text-button" @click="showCreate=false">取消</button>
          <button type="submit" class="command-button" :disabled="creating || !form.scopes.length"><KeyRound :size="15" />{{ creating ? '签发中' : '确认签发' }}</button>
        </div>
      </form>

      <div v-if="issuedKey" class="issued-key">
        <div><ShieldCheck :size="17" /><b>密钥已签发，仅显示本次</b></div>
        <code>{{ issuedKey }}</code>
        <button class="icon-button" title="复制 API Key" @click="copyIssuedKey"><Copy :size="16" /></button>
      </div>

      <div v-if="user" class="api-metrics">
        <div><span>近 7 日调用</span><b>{{ usage.totals.requests }}</b></div>
        <div><span>活跃租户</span><b>{{ usage.totals.tenants }}</b></div>
        <div><span>活跃 Key</span><b>{{ usage.totals.keys }}</b></div>
        <div><span>成功率</span><b>{{ usage.totals.success_rate }}%</b></div>
      </div>

      <div v-if="user" class="key-list" :aria-busy="keysLoading">
        <div class="key-row key-head"><span>租户与名称</span><span>Key 前缀</span><span>限流 / 日配额</span><span>状态</span><span></span></div>
        <div v-for="item in apiKeys" :key="item.key_id" class="key-row">
          <span><b>{{ item.tenant_id }}</b><small>{{ item.name }}</small></span>
          <code>{{ item.key_prefix }}</code>
          <span>{{ item.rate_limit_per_minute }}/分钟 · {{ item.daily_quota }}/日</span>
          <span :class="item.active ? 'key-active' : 'key-revoked'">{{ item.active ? '有效' : '已撤销' }}</span>
          <button class="icon-button danger-button" title="撤销 API Key" :disabled="!item.active" @click="revokeKey(item)"><Ban :size="15" /></button>
        </div>
        <div v-if="!keysLoading && !apiKeys.length" class="api-empty"><KeyRound :size="18" /><span>尚未签发 API Key。</span></div>
      </div>
    </section>

    <section class="security-note">
      <ShieldCheck :size="18" />
      <div><b>生产保护已启用</b><p>浏览器端只读取可公开的运行状态。敏感配置修改接口默认关闭，跨域来源限制为部署域名和本地开发环境。</p></div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { Ban, Bot, Copy, Database, Eye, KeyRound, LockKeyhole, Plus, RefreshCw, ScanFace, ShieldCheck } from 'lucide-vue-next'
import { ElMessageBox } from 'element-plus'
import { toast } from 'vue3-toastify'
import { useAuth } from '../composables/useAuth'

const info = reactive<any>({})
const { user } = useAuth()
const apiKeys = ref<any[]>([])
const keysLoading = ref(false)
const creating = ref(false)
const showCreate = ref(false)
const issuedKey = ref('')
const usage = reactive({ totals:{ requests:0, tenants:0, keys:0, success_rate:0 } })
const scopeOptions = [
  { value:'guardrail:check', label:'输入输出护栏' },
  { value:'guardrail:chat', label:'受保护模型调用' },
  { value:'content:check', label:'红线内容审核' },
  { value:'image:face', label:'人脸质量检查' },
  { value:'image:deepfake', label:'Deepfake 检测' },
  { value:'image:mllm', label:'多模态图片审核' },
  { value:'usage:read', label:'用量查询' },
]
const form = reactive({
  tenant_id:'competition-demo', name:'现场演示客户端',
  rate_limit_per_minute:60, daily_quota:5000,
  scopes:scopeOptions.map(item => item.value),
})

const statusItems = computed(() => [
  { label:'安全对话模型', value:info.chat_model || '未配置', ready:!!info.chat_model_configured, icon:Bot },
  { label:'多模态审核', value:info.mllm_model || '未配置', ready:!!info.mllm_configured, icon:Eye },
  { label:'人脸伪造检测', value:info.deepfake_configured ? '模型路径已就绪' : '待配置', ready:!!info.deepfake_configured, icon:ScanFace },
  { label:'红线知识库', value:info.rag_configured ? '检索引擎已就绪' : '待配置', ready:!!info.rag_configured, icon:Database },
])

async function apiJson(url: string, options?: RequestInit) {
  const response = await fetch(url, { credentials:'same-origin', ...options })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : data.detail?.message
    throw new Error(detail || `HTTP ${response.status}`)
  }
  return data
}

async function loadKeys() {
  if (!user.value) return
  keysLoading.value = true
  try {
    const [keys, stats] = await Promise.all([
      apiJson('/api/auth/api-keys'),
      apiJson('/api/auth/api-usage?days=7'),
    ])
    apiKeys.value = keys.items || []
    Object.assign(usage.totals, stats.totals || {})
  }
  catch (error) { toast.error(error instanceof Error ? error.message : '无法读取 API Key') }
  finally { keysLoading.value = false }
}

async function createKey() {
  creating.value = true
  try {
    const data = await apiJson('/api/auth/api-keys', {
      method:'POST', headers:{ 'Content-Type':'application/json' }, body:JSON.stringify(form),
    })
    issuedKey.value = data.key
    showCreate.value = false
    await loadKeys()
    toast.success('API Key 已签发')
  } catch (error) { toast.error(error instanceof Error ? error.message : '签发失败') }
  finally { creating.value = false }
}

async function copyIssuedKey() {
  await navigator.clipboard.writeText(issuedKey.value)
  toast.success('API Key 已复制')
}

async function revokeKey(item: any) {
  try {
    await ElMessageBox.confirm(`撤销 ${item.tenant_id} 的 ${item.key_prefix}？撤销后立即失效。`, '撤销 API Key', { type:'warning', confirmButtonText:'撤销', cancelButtonText:'取消' })
    await apiJson(`/api/auth/api-keys/${encodeURIComponent(item.key_id)}`, { method:'DELETE' })
    issuedKey.value = ''
    await loadKeys()
    toast.success('API Key 已撤销')
  } catch (error: any) {
    if (error !== 'cancel' && error !== 'close') toast.error(error instanceof Error ? error.message : '撤销失败')
  }
}

onMounted(async () => {
  try {
    const response = await fetch('/api/system/info')
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    Object.assign(info, await response.json())
  } catch {
    toast.error('无法读取系统运行状态')
  }
})
watch(user, value => { if (value) loadKeys(); else apiKeys.value = [] }, { immediate:true })
</script>

<style scoped>
.settings-page{max-width:1050px;margin:0 auto;display:flex;flex-direction:column;gap:18px}.page-head{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;padding:4px 2px}.eyebrow{color:var(--primary);font:10px ui-monospace,monospace}.page-head h1{margin:7px 0;font-size:24px;letter-spacing:0}.page-head p{max-width:700px;margin:0;color:var(--muted);font-size:13px;line-height:1.7}.managed-badge{display:flex;align-items:center;gap:7px;padding:8px 11px;color:var(--primary);border:1px solid rgba(45,212,191,.22);border-radius:5px;background:rgba(45,212,191,.06);font-size:11px;white-space:nowrap}.status-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.status-card{position:relative;display:flex;align-items:center;gap:12px;min-width:0;padding:15px;border:1px solid var(--line);border-radius:7px;background:var(--surface-2)}.status-icon{display:grid;place-items:center;width:38px;height:38px;flex:0 0 38px;color:var(--primary);border:1px solid rgba(45,212,191,.18);border-radius:5px;background:rgba(45,212,191,.05)}.status-card span{display:block;margin-bottom:4px;color:var(--faint);font-size:9px}.status-card b{display:block;max-width:320px;overflow:hidden;color:var(--text);font-size:12px;font-weight:500;text-overflow:ellipsis;white-space:nowrap}.status-card>i{position:absolute;top:13px;right:13px;width:6px;height:6px;border-radius:50%}.status-card>i.online{background:var(--success);box-shadow:0 0 8px rgba(52,211,153,.6)}.status-card>i.offline{background:var(--warning)}.deployment-card{padding:18px}.info-rows{margin-top:12px}.info-rows div{display:grid;grid-template-columns:145px minmax(0,1fr);gap:15px;padding:11px 2px;border-bottom:1px solid var(--line)}.info-rows div:last-child{border-bottom:0}.info-rows span{color:var(--faint);font-size:11px}.info-rows b{color:var(--text);font-size:12px;font-weight:500;word-break:break-word}.security-note{display:flex;align-items:flex-start;gap:11px;padding:14px 16px;color:var(--success);border:1px solid rgba(52,211,153,.2);border-radius:7px;background:rgba(52,211,153,.05)}.security-note svg{flex:0 0 auto}.security-note b{font-size:11px}.security-note p{margin:5px 0 0;color:var(--muted);font-size:11px;line-height:1.6}@media(max-width:720px){.page-head{align-items:flex-start;flex-direction:column}.status-grid{grid-template-columns:1fr}.info-rows div{grid-template-columns:1fr;gap:5px}.page-head h1{font-size:20px}}
.api-card{padding:18px}.api-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:18px}.api-heading .card-title{margin-bottom:6px}.api-heading p{margin:0;color:var(--muted);font-size:11px;line-height:1.6}.api-actions,.form-actions{display:flex;align-items:center;gap:8px}.icon-button,.command-button,.text-button{display:inline-flex;align-items:center;justify-content:center;gap:7px;height:34px;border:1px solid var(--line);border-radius:6px;background:#fff;color:var(--muted);cursor:pointer}.icon-button{width:34px}.command-button{padding:0 12px;border-color:var(--primary);background:var(--primary);color:#fff}.text-button{padding:0 12px}.icon-button:disabled,.command-button:disabled{opacity:.45;cursor:not-allowed}.danger-button:not(:disabled){color:var(--danger)}.api-empty{display:flex;align-items:center;justify-content:center;gap:8px;min-height:82px;color:var(--faint);font-size:12px}.key-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px;margin-top:16px;padding:16px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}.key-form>label{display:flex;flex-direction:column;gap:6px;color:var(--muted);font-size:11px}.key-form input:not([type=checkbox]){width:100%;height:36px;padding:0 10px;border:1px solid var(--line);border-radius:5px;background:var(--surface-2);color:var(--text)}.key-form fieldset{grid-column:1/-1;display:flex;flex-wrap:wrap;gap:8px 16px;margin:0;padding:12px;border:1px solid var(--line);border-radius:6px}.key-form legend{padding:0 5px;color:var(--muted);font-size:11px}.scope-option{display:flex;align-items:center;gap:6px;color:var(--text);font-size:11px}.form-actions{grid-column:1/-1;justify-content:flex-end}.issued-key{display:grid;grid-template-columns:1fr auto;gap:9px;margin-top:14px;padding:13px;border:1px solid rgba(22,128,94,.22);border-radius:6px;background:rgba(22,128,94,.05)}.issued-key>div{grid-column:1/-1;display:flex;align-items:center;gap:7px;color:var(--success);font-size:11px}.issued-key code{min-width:0;padding:8px;overflow:auto;border:1px solid var(--line);border-radius:4px;background:#fff;color:var(--text);font-size:11px;white-space:nowrap}.key-list{margin-top:15px;border-top:1px solid var(--line)}.key-row{display:grid;grid-template-columns:minmax(160px,1.35fr) minmax(130px,1fr) minmax(145px,1fr) 65px 36px;align-items:center;gap:12px;min-height:58px;padding:8px 2px;border-bottom:1px solid var(--line);color:var(--muted);font-size:11px}.key-row>span:first-child b,.key-row>span:first-child small{display:block}.key-row>span:first-child b{color:var(--text);font-size:11px}.key-row>span:first-child small{margin-top:3px;color:var(--faint)}.key-row code{overflow:hidden;color:var(--primary);font-size:11px;text-overflow:ellipsis}.key-head{min-height:34px;color:var(--faint);font-size:10px}.key-active{color:var(--success)}.key-revoked{color:var(--faint)}
.api-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;margin-top:15px;border:1px solid var(--line);border-radius:6px;background:var(--line);overflow:hidden}.api-metrics>div{padding:11px 13px;background:var(--surface-2)}.api-metrics span,.api-metrics b{display:block}.api-metrics span{color:var(--faint);font-size:9px}.api-metrics b{margin-top:5px;color:var(--text);font:600 16px ui-monospace,monospace}
@media(max-width:800px){.api-heading{flex-direction:column}.key-row{grid-template-columns:1fr auto}.key-head{display:none}.key-row>span,.key-row>code{grid-column:1}.key-row>button{grid-column:2;grid-row:1}.key-form{grid-template-columns:1fr}.key-form fieldset,.form-actions{grid-column:1}}
@media(max-width:560px){.api-metrics{grid-template-columns:1fr 1fr}}
</style>
