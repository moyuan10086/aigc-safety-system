<template>
  <section class="audit-panel">
    <div v-if="authRequired" class="locked-state">
      <div class="lock-mark"><LockKeyhole :size="24" /></div>
      <h2>安全日志受访问控制</h2>
      <p>登录审核员账号后可查看日志、原始证据与导出记录。</p>
      <button type="button" @click="openLogin"><LogIn :size="16" />审核员登录</button>
    </div>

    <template v-else>
      <div class="audit-heading">
        <div><p>AUDIT TELEMETRY</p><h2>安全审计日志</h2><span v-if="stats">{{ stats.retention_days }} 天留存 · AES-GCM 证据隔离 · 哈希链{{ stats.chain_valid ? '完整' : '异常' }}</span></div>
        <div class="heading-actions">
          <label class="auto-refresh"><input type="checkbox" :checked="autoRefresh" @change="setAutoRefresh(($event.target as HTMLInputElement).checked)"><span></span>自动刷新</label>
          <a class="command-button" :href="exportUrl" title="导出当前筛选结果"><Download :size="16" /><b>CSV</b></a>
          <button class="icon-button" type="button" title="刷新日志" :disabled="loading" @click="refresh"><RefreshCw :size="17" :class="{ spinning: loading }" /></button>
        </div>
      </div>

      <div class="metric-grid">
        <article><span>24H 事件</span><strong>{{ stats?.last_24h ?? '-' }}</strong><small>累计 {{ stats?.total ?? '-' }}</small></article>
        <article class="danger"><span>高风险事件</span><strong>{{ stats?.high_risk ?? '-' }}</strong><small>需重点关注</small></article>
        <article class="warning"><span>阻断 / 拒绝</span><strong>{{ stats?.blocked ?? '-' }}</strong><small>近 24 小时</small></article>
        <article><span>来源 IP</span><strong>{{ stats?.unique_clients ?? '-' }}</strong><small>近 24 小时去重</small></article>
        <article :class="stats?.chain_valid ? 'success' : 'danger'"><span>证据链状态</span><strong class="chain-value">{{ stats?.chain_valid ? '完整' : '异常' }}</strong><small>SHA-256 哈希链</small></article>
      </div>

      <div class="filter-bar">
        <label class="search-box"><Search :size="15" /><input v-model="filters.keyword" type="search" placeholder="事件、IP、操作者、风险代码"></label>
        <select v-model="filters.module" aria-label="模块筛选"><option value="">全部模块</option><option value="guardrail">安全护栏</option><option value="detect">内容审核</option><option value="auth">身份认证</option><option value="system">系统</option><option value="audit">审计</option><option value="garak">主动扫描</option></select>
        <select v-model="filters.severity" aria-label="等级筛选"><option value="">全部等级</option><option value="critical">严重</option><option value="high">高风险</option><option value="warning">关注</option><option value="info">信息</option></select>
        <select v-model="filters.outcome" aria-label="结果筛选"><option value="">全部结果</option><option value="blocked">阻断</option><option value="denied">拒绝</option><option value="review">复核</option><option value="allowed">放行</option><option value="success">成功</option><option value="error">异常</option></select>
      </div>

      <div class="log-table-wrap">
        <table>
          <thead><tr><th>时间</th><th>等级</th><th>模块 / 动作</th><th>事件摘要</th><th>操作者 / 来源</th><th>结果</th><th>延迟</th><th aria-label="详情"></th></tr></thead>
          <tbody>
            <tr v-for="item in items" :key="item.id" @click="selected = item">
              <td class="time-cell"><b>{{ timePart(item.occurred_at) }}</b><span>{{ datePart(item.occurred_at) }}</span></td>
              <td><span class="severity-dot" :class="item.severity"></span>{{ severityLabel[item.severity] }}</td>
              <td><b class="module-name">{{ moduleLabel[item.module] || item.module }}</b><span class="action-name">{{ item.action }}</span></td>
              <td class="summary-cell"><b>{{ item.summary }}</b><span v-if="item.risk_code">{{ item.risk_code }} · {{ formatRisk(item.risk_score) }}</span></td>
              <td><b>{{ item.actor || '-' }}</b><span>{{ item.client_ip || '-' }}</span></td>
              <td><span class="outcome-badge" :class="item.outcome">{{ outcomeLabel[item.outcome] || item.outcome }}</span></td>
              <td class="mono-cell">{{ item.latency_ms ?? '-' }} ms</td>
              <td><button class="row-action" type="button" title="查看取证详情" @click.stop="selected = item"><ChevronRight :size="16" /></button></td>
            </tr>
            <tr v-if="!loading && !items.length"><td colspan="8" class="empty-row">暂无符合条件的日志</td></tr>
          </tbody>
        </table>
        <div v-if="loading && !items.length" class="table-loading"><LoaderCircle :size="20" />正在读取审计链</div>
      </div>

      <div class="table-foot">
        <span>共 {{ total }} 条 · 第 {{ page }} / {{ Math.max(1, Math.ceil(total / pageSize)) }} 页</span>
        <div><button type="button" :disabled="page <= 1" title="上一页" @click="page--"><ChevronLeft :size="16" /></button><button type="button" :disabled="page * pageSize >= total" title="下一页" @click="page++"><ChevronRight :size="16" /></button></div>
      </div>
      <p v-if="error" class="panel-error">{{ error }}</p>
    </template>
    <AuditLogDetail :event="selected" @close="selected = null" />
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { ChevronLeft, ChevronRight, Download, LoaderCircle, LockKeyhole, LogIn, RefreshCw, Search } from 'lucide-vue-next'
import AuditLogDetail from './AuditLogDetail.vue'
import { useAuth } from '../../composables/useAuth'
import { useAuditLogs, type AuditEvent } from '../../composables/useAuditLogs'

const selected = ref<AuditEvent | null>(null)
const { user } = useAuth()
const { items, stats, total, page, pageSize, loading, error, authRequired, autoRefresh, filters, exportUrl, refresh, setAutoRefresh, openLogin } = useAuditLogs()
const severityLabel = { info: '信息', warning: '关注', high: '高风险', critical: '严重' }
const outcomeLabel: Record<string, string> = { success: '成功', allowed: '放行', review: '复核', blocked: '阻断', denied: '拒绝', error: '异常' }
const moduleLabel: Record<string, string> = { guardrail: '安全护栏', detect: '内容审核', auth: '身份认证', system: '系统', audit: '审计', garak: '主动扫描' }
const dateFormatter = new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit' })
const timeFormatter = new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
const datePart = (value: string) => dateFormatter.format(new Date(value))
const timePart = (value: string) => timeFormatter.format(new Date(value))
const formatRisk = (value?: number) => value == null ? '-' : value.toFixed(2)
onMounted(refresh)
watch(user, (current, previous) => { if (current && !previous) refresh() })
</script>

<style scoped>
.audit-panel{width:100%}.locked-state{min-height:420px;display:flex;align-items:center;justify-content:center;flex-direction:column;text-align:center;background:var(--surface);border:1px solid var(--line);border-radius:8px}.lock-mark{width:54px;height:54px;display:grid;place-items:center;color:var(--primary);background:var(--surface-3);border:1px solid var(--line);border-radius:7px}.locked-state h2{margin:15px 0 5px;font-size:16px}.locked-state p{margin:0;color:var(--muted);font-size:11px}.locked-state button{height:38px;margin-top:18px;display:flex;align-items:center;gap:7px;padding:0 14px;color:#fff;background:var(--primary);border:0;border-radius:6px;font-size:12px;font-weight:650;cursor:pointer}
.audit-heading{display:flex;align-items:flex-end;gap:20px;margin-bottom:16px}.audit-heading p{margin:0 0 5px;color:var(--primary);font:700 9px/1 ui-monospace,monospace}.audit-heading h2{margin:0 0 5px;font-size:18px}.audit-heading span{color:var(--faint);font-size:10px}.heading-actions{margin-left:auto;display:flex;align-items:center;gap:8px}.icon-button,.row-action,.table-foot button{width:36px;height:36px;display:grid;place-items:center;color:var(--muted);background:var(--surface);border:1px solid var(--line);border-radius:6px;cursor:pointer}.icon-button:hover,.row-action:hover,.table-foot button:hover:not(:disabled){color:var(--primary);border-color:var(--line-bright);background:var(--surface-3)}.icon-button:disabled,.table-foot button:disabled{opacity:.4;cursor:not-allowed}.command-button{height:36px;display:flex;align-items:center;gap:7px;padding:0 10px;color:var(--primary);background:var(--surface);border:1px solid var(--line);border-radius:6px;text-decoration:none;font-size:10px}.auto-refresh{height:36px;display:flex;align-items:center;gap:7px;padding:0 10px;color:var(--muted);background:var(--surface);border:1px solid var(--line);border-radius:6px;font-size:10px;cursor:pointer}.auto-refresh input{position:absolute;opacity:0;pointer-events:none}.auto-refresh span{width:24px;height:13px;position:relative;background:var(--line-bright);border-radius:7px}.auto-refresh span::after{content:'';width:9px;height:9px;position:absolute;left:2px;top:2px;background:#fff;border-radius:50%;transition:transform .16s}.auto-refresh input:checked+span{background:var(--success)}.auto-refresh input:checked+span::after{transform:translateX(11px)}
.metric-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin-bottom:12px}.metric-grid article{min-width:0;padding:13px 14px;background:var(--surface);border:1px solid var(--line);border-top:3px solid var(--primary);border-radius:7px;box-shadow:var(--shadow-sm)}.metric-grid article.warning{border-top-color:var(--warning)}.metric-grid article.danger{border-top-color:var(--danger)}.metric-grid article.success{border-top-color:var(--success)}.metric-grid span{display:block;color:var(--faint);font-size:9px}.metric-grid strong{display:block;margin:7px 0 3px;font:700 24px/1 ui-monospace,monospace}.metric-grid .chain-value{font:700 17px/1.25 inherit}.metric-grid small{color:var(--muted);font-size:9px}
.filter-bar{display:grid;grid-template-columns:minmax(240px,1fr) repeat(3,140px);gap:8px;margin-bottom:10px}.search-box{height:38px;display:flex;align-items:center;gap:8px;padding:0 11px;color:var(--faint);background:var(--surface);border:1px solid var(--line);border-radius:6px}.search-box:focus-within{color:var(--primary);border-color:var(--primary)}.search-box input{width:100%;border:0;outline:0;background:transparent;color:var(--text);font-size:11px}.filter-bar select{height:38px;padding:0 10px;color:var(--muted);background:var(--surface);border:1px solid var(--line);border-radius:6px;outline:0;font-size:11px}.filter-bar select:focus{border-color:var(--primary)}
.log-table-wrap{position:relative;min-height:290px;overflow:auto;background:var(--surface);border:1px solid var(--line);border-radius:7px;box-shadow:var(--shadow-sm)}table{width:100%;min-width:1000px;border-collapse:collapse;table-layout:fixed}th{height:38px;padding:0 10px;text-align:left;color:var(--faint);background:var(--surface-2);border-bottom:1px solid var(--line);font-size:9px;font-weight:650}th:nth-child(1){width:85px}th:nth-child(2){width:82px}th:nth-child(3){width:150px}th:nth-child(5){width:140px}th:nth-child(6){width:78px}th:nth-child(7){width:75px}th:nth-child(8){width:45px}td{height:56px;padding:7px 10px;border-bottom:1px solid var(--line);color:var(--muted);font-size:10px;vertical-align:middle}tbody tr{cursor:pointer}tbody tr:hover{background:var(--surface-2)}td b,td span{display:block}.time-cell b{color:var(--text);font:600 11px ui-monospace,monospace}.time-cell span,.action-name,td>span{margin-top:3px;color:var(--faint);font-size:9px}.severity-dot{width:7px;height:7px;margin:0 6px 0 0!important;display:inline-block!important;background:var(--primary);border-radius:50%}.severity-dot.warning{background:var(--warning)}.severity-dot.high,.severity-dot.critical{background:var(--danger);box-shadow:0 0 0 3px rgba(207,63,79,.1)}.module-name,.summary-cell b,td>b{overflow:hidden;color:var(--text);font-weight:600;text-overflow:ellipsis;white-space:nowrap}.summary-cell span{color:var(--warning)}.outcome-badge{width:max-content;margin:0!important;padding:3px 7px;border-radius:3px;background:var(--surface-3);color:var(--muted)!important}.outcome-badge.allowed,.outcome-badge.success{color:var(--success)!important;background:rgba(22,128,94,.09)}.outcome-badge.review{color:var(--warning)!important;background:rgba(184,111,18,.09)}.outcome-badge.blocked,.outcome-badge.denied,.outcome-badge.error{color:var(--danger)!important;background:rgba(207,63,79,.08)}.mono-cell{font-family:ui-monospace,monospace}.row-action{width:30px;height:30px;border-color:transparent;background:transparent}.empty-row{height:180px!important;text-align:center;color:var(--faint)}.table-loading{position:absolute;inset:38px 0 0;display:flex;align-items:center;justify-content:center;gap:8px;color:var(--muted);background:rgba(255,255,255,.84);font-size:11px}.table-loading svg,.spinning{animation:spin .9s linear infinite}
.table-foot{display:flex;align-items:center;margin-top:10px;color:var(--faint);font-size:9px}.table-foot div{display:flex;gap:5px;margin-left:auto}.table-foot button{width:32px;height:30px}.panel-error{color:var(--danger);font-size:10px}@keyframes spin{to{transform:rotate(360deg)}}
@media(max-width:1100px){.metric-grid{grid-template-columns:repeat(3,1fr)}.filter-bar{grid-template-columns:1fr 1fr}.search-box{grid-column:1/-1}}@media(max-width:680px){.audit-heading{align-items:flex-start;flex-direction:column}.heading-actions{width:100%;margin-left:0}.auto-refresh{margin-right:auto}.command-button b{display:none}.metric-grid{grid-template-columns:1fr 1fr}.filter-bar{grid-template-columns:1fr}.search-box{grid-column:auto}}
</style>
