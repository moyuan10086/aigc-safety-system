<template>
  <div class="report-page">
    <div class="view-switcher">
      <div><p>TRACE &amp; EVIDENCE</p><h1>审计与取证</h1></div>
      <div class="segmented" role="tablist" aria-label="审计视图">
        <button type="button" :class="{ active: activeView === 'reports' }" @click="activeView = 'reports'"><FileText :size="15" />检测报告</button>
        <button type="button" :class="{ active: activeView === 'logs' }" @click="activeView = 'logs'"><ShieldCheck :size="15" />安全日志</button>
      </div>
    </div>

    <AuditLogPanel v-if="activeView === 'logs'" />
    <div v-else class="report-list">
    <!-- 统计卡片 -->
    <div v-if="stats" class="card" style="margin-bottom:16px">
      <div class="card-title">检测统计</div>
      <div style="display:flex;gap:24px">
        <div class="stat-item"><div class="stat-num">{{ stats.total }}</div><div class="stat-label">总检测数</div></div>
        <div class="stat-item"><div class="stat-num" style="color:#dc2626">{{ stats.fake_count }}</div><div class="stat-label">伪造图像</div></div>
        <div class="stat-item"><div class="stat-num" style="color:#f59e0b">{{ stats.risk_count }}</div><div class="stat-label">需复核/内容风险</div></div>
        <div class="stat-item"><div class="stat-num" style="color:#16a34a">{{ stats.clear_count }}</div><div class="stat-label">无风险记录</div></div>
      </div>
    </div>

    <div v-if="loading" class="card" style="text-align:center;padding:32px;color:#94a3b8">
      加载报告中...
    </div>
    <div v-else-if="reports.length === 0" class="card">
      <el-empty description="暂无报告，请前往图像检测页面进行检测" />
    </div>
    <div v-for="r in reports" :key="r.id" class="card" style="margin-bottom:16px">
      <div class="card-title">
        {{ r.filename || '文本审核' }}
        <span style="margin-left:auto;font-size:11px;color:#94a3b8;font-weight:400">{{ r.created_at?.slice(0,19).replace('T',' ') }}</span>
        <button @click="copyId(r.id)" style="margin-left:8px;font-size:11px;color:#94a3b8;background:none;border:none;cursor:pointer;padding:2px 6px;border-radius:4px;hover:background:#f1f5f9" title="复制报告ID">📋</button>
        <a :href="`/api/detect/report/${r.id}/download`" class="download-link">JSON 下载</a>
        <a :href="`/api/detect/report/${r.id}/download/md`" class="download-link">MD 下载</a>
      </div>

      <!-- 检测结果摘要 -->
      <div class="report-grid">
        <div v-if="r.deepfake">
          <div class="section-label">Deepfake</div>
          <span class="badge" :class="r.deepfake.label==='fake'?'badge-danger':r.deepfake.label==='skipped'?'badge-warn':'badge-success'">
            {{ r.deepfake.label==='fake'?'伪造':r.deepfake.label==='skipped'?'非人脸':'真实' }}
          </span>
          <span style="font-size:12px;color:#64748b;margin-left:8px">得分 {{ (r.deepfake.score*100).toFixed(1) }}%</span>
        </div>
        <div v-if="r.mllm">
          <div class="section-label">MLLM</div>
          <span class="badge" :class="r.mllm.verdict==='fake'?'badge-danger':r.mllm.verdict==='real'?'badge-success':'badge-warn'">
            {{ r.mllm.verdict==='fake'?'伪造':r.mllm.verdict==='real'?'真实':'不确定' }}
          </span>
        </div>
        <div v-if="r.rag">
          <div class="section-label">知识库检索增强审核</div>
          <span class="badge" :class="r.rag.safe?'badge-success':'badge-danger'">{{ r.rag.safe?'安全':'风险' }}</span>
          <span style="font-size:12px;color:#64748b;margin-left:8px">{{ r.rag.risk_level?.toUpperCase() }}</span>
        </div>
        <div v-if="r.content_safety">
          <div class="section-label">视觉内容安全</div>
          <span class="badge" :class="contentSafetyClass(r.content_safety.verdict)">{{ contentSafetyLabel(r.content_safety.verdict) }}</span>
          <span style="font-size:12px;color:#64748b;margin-left:8px">风险 {{ formatPercent(r.content_safety.risk_score) }}</span>
          <span v-if="r.content_safety.categories?.length" class="category-summary">{{ categorySummary(r.content_safety.categories) }}</span>
        </div>
      </div>

      <!-- MLLM 综合分析（Markdown 渲染） -->
      <section v-if="r.summary" class="markdown-report">
        <div class="section-label">综合分析报告 · MARKDOWN PREVIEW</div>
        <div class="md-body" v-html="renderMd(r.summary)" />
      </section>
    </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { useClipboard } from '@vueuse/core'
import { toast } from 'vue3-toastify'
import { FileText, ShieldCheck } from 'lucide-vue-next'
import AuditLogPanel from '../components/audit/AuditLogPanel.vue'

const { copy } = useClipboard()
const activeView = ref<'reports' | 'logs'>('reports')

const reports = ref<any[]>([])
const stats = ref<any>(null)
const loading = ref(false)
const reportsLoaded = ref(false)

function renderMd(md: string): string {
  return DOMPurify.sanitize(marked.parse(md, { gfm: true, breaks: true }) as string)
}

const copyId = async (id: string) => {
  await copy(id)
  toast.success('报告ID已复制')
}

async function loadReports() {
  if (reportsLoaded.value || loading.value) return
  loading.value = true
  try {
    const r = await fetch('/api/detect/history')
    if (r.ok) {
      const d = await r.json()
      stats.value = { total: d.total, fake_count: d.fake_count, risk_count: d.risk_count, clear_count: d.clear_count }
      const full = await Promise.all(
        d.reports.map((item: any) =>
          fetch(`/api/detect/report/${item.id}`).then(r => r.ok ? r.json() : null)
        )
      )
      reports.value = full.filter(Boolean)
      reportsLoaded.value = true
    }
  } finally {
    loading.value = false
  }
}

watch(activeView, view => { if (view === 'reports') loadReports() }, { immediate: true })
function contentSafetyClass(verdict: string) { return verdict === 'unsafe' ? 'badge-danger' : verdict === 'safe' ? 'badge-success' : 'badge-warn' }
function contentSafetyLabel(verdict: string) { return ({ safe: '安全', review: '人工复核', unsafe: '阻断' } as Record<string, string>)[verdict] || '结论不足' }
function formatPercent(value: unknown) { const score = Number(value); return Number.isFinite(score) ? `${(score * 100).toFixed(1)}%` : '未知' }
function categorySummary(items: any[]) { return items.slice(0, 3).map(item => `${item.label || item.code} ${formatPercent(item.confidence)}`).join(' · ') }
</script>

<style scoped>
.report-page{width:100%;max-width:1500px;margin:0 auto}.report-list{max-width:1000px;margin:0 auto}.view-switcher{display:flex;align-items:flex-end;gap:18px;margin-bottom:18px}.view-switcher p{margin:0 0 5px;color:var(--primary);font:700 9px/1 ui-monospace,monospace}.view-switcher h1{margin:0;font-size:20px}.segmented{margin-left:auto;display:flex;padding:3px;background:var(--surface);border:1px solid var(--line);border-radius:7px;box-shadow:var(--shadow-sm)}.segmented button{height:32px;display:flex;align-items:center;gap:7px;padding:0 12px;color:var(--muted);background:transparent;border:0;border-radius:5px;font-size:11px;cursor:pointer}.segmented button.active{color:#fff;background:var(--primary);font-weight:650}@media(max-width:560px){.view-switcher{align-items:flex-start;flex-direction:column}.segmented{width:100%;margin-left:0}.segmented button{flex:1;justify-content:center}}
.stat-item { text-align:center; flex:1 }
.stat-num { font-size:24px; font-weight:700; color:var(--text) }
.stat-label { font-size:11px; color:var(--muted); margin-top:2px }
.report-grid { display:flex;flex-direction:column;gap:12px;margin-top:8px }
.badge { display:inline-flex;padding:3px 9px;border-radius:4px;font-size:11px;font-weight:600 }
.badge-success { background:rgba(52,211,153,.1);color:var(--success) }
.badge-danger { background:rgba(251,113,133,.1);color:var(--danger) }
.badge-warn { background:rgba(245,158,11,.1);color:var(--warning) }
.download-link{margin-left:8px;font-size:11px;color:var(--primary);text-decoration:none}.markdown-report{margin-top:16px;padding-top:14px;border-top:1px solid var(--line)}.markdown-report>.section-label{margin-bottom:10px}.md-body{overflow-wrap:anywhere;color:var(--muted);font-size:13px;line-height:1.75}
.category-summary{display:block;margin-top:6px;color:var(--muted);font-size:11px;line-height:1.5}
.md-body :deep(h1),.md-body :deep(h2),.md-body :deep(h3) { font-weight:700;margin:12px 0 6px;color:var(--text) }
.md-body :deep(h2) { font-size:14px }
.md-body :deep(h3) { font-size:13px }
.md-body :deep(ul),.md-body :deep(ol) { padding-left:20px;margin:6px 0 }
.md-body :deep(li) { margin:3px 0 }
.md-body :deep(strong) { color:var(--text) }
.md-body :deep(p) { margin:6px 0 }
.md-body :deep(a){color:var(--primary);text-decoration:none}.md-body :deep(blockquote){margin:10px 0;padding:8px 12px;color:var(--muted);background:var(--surface-2);border-left:3px solid var(--primary)}.md-body :deep(hr){margin:14px 0;border:0;border-top:1px solid var(--line)}.md-body :deep(pre){max-width:100%;margin:10px 0;padding:12px;overflow:auto;color:var(--text);background:var(--surface-3);border:1px solid var(--line);border-radius:6px}.md-body :deep(code){padding:1px 5px;background:var(--surface-3);border-radius:3px;font:12px/1.6 ui-monospace,SFMono-Regular,Consolas,monospace}.md-body :deep(pre code){padding:0;background:transparent}.md-body :deep(table){width:100%;margin:10px 0;border-collapse:collapse;font-size:12px}.md-body :deep(th),.md-body :deep(td){padding:7px 9px;border:1px solid var(--line);text-align:left}.md-body :deep(th){color:var(--text);background:var(--surface-2)}
</style>
