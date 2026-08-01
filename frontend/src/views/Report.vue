<template>
  <div style="max-width:900px;margin:0 auto">
    <!-- 统计卡片 -->
    <div v-if="stats" class="card" style="margin-bottom:16px">
      <div class="card-title">检测统计</div>
      <div style="display:flex;gap:24px">
        <div class="stat-item"><div class="stat-num">{{ stats.total }}</div><div class="stat-label">总检测数</div></div>
        <div class="stat-item"><div class="stat-num" style="color:#dc2626">{{ stats.fake_count }}</div><div class="stat-label">伪造图像</div></div>
        <div class="stat-item"><div class="stat-num" style="color:#f59e0b">{{ stats.risk_count }}</div><div class="stat-label">内容风险</div></div>
        <div class="stat-item"><div class="stat-num" style="color:#16a34a">{{ stats.total - stats.fake_count - stats.risk_count }}</div><div class="stat-label">安全通过</div></div>
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
        <a :href="`/api/detect/report/${r.id}/download`" style="margin-left:8px;font-size:12px;color:#f472b6">JSON</a>
        <a :href="`/api/detect/report/${r.id}/download/md`" style="margin-left:8px;font-size:12px;color:#f472b6">MD</a>
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
          <div class="section-label">RAG审核</div>
          <span class="badge" :class="r.rag.safe?'badge-success':'badge-danger'">{{ r.rag.safe?'安全':'风险' }}</span>
          <span style="font-size:12px;color:#64748b;margin-left:8px">{{ r.rag.risk_level?.toUpperCase() }}</span>
        </div>
      </div>

      <!-- MLLM 综合分析（Markdown 渲染） -->
      <div v-if="r.summary" style="margin-top:16px;border-top:1px solid #fce7f3;padding-top:14px">
        <div class="section-label" style="margin-bottom:8px">综合分析报告</div>
        <div class="md-body" v-html="renderMd(r.summary)" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { marked } from 'marked'
import { useClipboard } from '@vueuse/core'
import { toast } from 'vue3-toastify'

const { copy } = useClipboard()

const reports = ref<any[]>([])
const stats = ref<any>(null)
const loading = ref(true)

function renderMd(md: string): string {
  return marked.parse(md) as string
}

const copyId = async (id: string) => {
  await copy(id)
  toast.success('报告ID已复制')
}

onMounted(async () => {
  try {
    const r = await fetch('/api/detect/history')
    if (r.ok) {
      const d = await r.json()
      stats.value = { total: d.total, fake_count: d.fake_count, risk_count: d.risk_count }
      const full = await Promise.all(
        d.reports.map((item: any) =>
          fetch(`/api/detect/report/${item.id}`).then(r => r.ok ? r.json() : null)
        )
      )
      reports.value = full.filter(Boolean)
    }
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.stat-item { text-align:center; flex:1 }
.stat-num { font-size:24px; font-weight:700; color:#1e293b }
.stat-label { font-size:11px; color:#94a3b8; margin-top:2px }
.report-grid { display:flex;flex-direction:column;gap:12px;margin-top:8px }
.badge { display:inline-flex;padding:2px 10px;border-radius:9999px;font-size:11px;font-weight:600 }
.badge-success { background:#dcfce7;color:#16a34a }
.badge-danger { background:#fee2e2;color:#dc2626 }
.badge-warn { background:#fef9c3;color:#ca8a04 }
.md-body { font-size:13px;line-height:1.7;color:#334155 }
.md-body :deep(h1),.md-body :deep(h2),.md-body :deep(h3) { font-weight:700;margin:12px 0 6px;color:#1e293b }
.md-body :deep(h2) { font-size:14px }
.md-body :deep(h3) { font-size:13px }
.md-body :deep(ul),.md-body :deep(ol) { padding-left:20px;margin:6px 0 }
.md-body :deep(li) { margin:3px 0 }
.md-body :deep(strong) { color:#1e293b }
.md-body :deep(p) { margin:6px 0 }
.md-body :deep(code) { background:#f1f5f9;padding:1px 5px;border-radius:4px;font-size:12px }
</style>
