<template>
  <div class="detect-page">
    <title>图像检测 - AIGC安全系统</title>

    <!-- 顶部信息网格：仿 NapCat QQInfo + SystemInfo + SystemStatus -->
    <div class="top-grid">
      <!-- 图像信息卡 -->
      <div class="card info-card">
        <div class="avatar-wrap">
          <img v-if="preview" :src="preview" class="avatar-img" alt="preview" />
          <div v-else class="avatar-placeholder">
            <!-- 空状态插画 -->
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
              <circle cx="24" cy="24" r="20" fill="#fdf2f8" stroke="#f9a8d4" stroke-width="1.5"/>
              <circle cx="24" cy="20" r="6" fill="#fce7f3" stroke="#f472b6" stroke-width="1.5"/>
              <path d="M10 38c0-7.7 6.3-14 14-14s14 6.3 14 14" stroke="#f472b6" stroke-width="1.5" stroke-linecap="round" fill="none"/>
            </svg>
          </div>
          <div class="avatar-dot" :class="file ? 'dot-ready' : 'dot-idle'"></div>
        </div>
        <div class="info-text">
          <div class="info-name">{{ file?.name || '未上传图像' }}</div>
          <div class="info-sub">{{ file ? formatSize(file.size) : '等待上传' }}</div>
        </div>
      </div>

      <!-- 系统信息卡 -->
      <div class="card sys-card">
        <div class="card-title">系统信息</div>
        <div class="sys-rows">
          <div class="sys-row">
            <span class="sys-dot"></span>
            <span class="sys-label">Deepfake 模型</span>
            <span class="sys-val">CLIP-ViT-L/14</span>
          </div>
          <div class="sys-row">
            <span class="sys-dot"></span>
            <span class="sys-label">MLLM 模型</span>
            <span class="sys-val">{{ mllmModel }}</span>
          </div>
          <div class="sys-row">
            <span class="sys-dot"></span>
            <span class="sys-label">RAG 引擎</span>
            <span class="sys-val">ChromaDB</span>
          </div>
        </div>
      </div>

      <!-- 得分环形图卡 -->
      <div class="card ring-card">
        <div class="ring-wrap">
          <div class="ring-item">
            <svg viewBox="0 0 100 100" class="ring-svg">
              <circle cx="50" cy="50" r="38" class="ring-bg" />
              <circle cx="50" cy="50" r="38" class="ring-fill ring-pink"
                :style="{ strokeDashoffset: 239 - (results.deepfake?.score || 0) * 239 }" />
            </svg>
            <div class="ring-center">
              <div class="ring-val">{{ results.deepfake ? (results.deepfake.score * 100).toFixed(0) : '—' }}</div>
              <div class="ring-unit" v-if="results.deepfake">%</div>
            </div>
            <div class="ring-label">伪造得分</div>
          </div>
          <div class="ring-item">
            <svg viewBox="0 0 100 100" class="ring-svg">
              <circle cx="50" cy="50" r="38" class="ring-bg" />
              <circle cx="50" cy="50" r="38" class="ring-fill ring-purple"
                :style="{ strokeDashoffset: 239 - (results.mllm?.confidence || 0) * 239 }" />
            </svg>
            <div class="ring-center">
              <div class="ring-val ring-val-purple">{{ results.mllm ? (results.mllm.confidence * 100).toFixed(0) : '—' }}</div>
              <div class="ring-unit ring-val-purple" v-if="results.mllm">%</div>
            </div>
            <div class="ring-label">MLLM置信度</div>
            <div v-if="results.mllm" style="font-size:10px;text-align:center;margin-top:2px"
                 :style="{color: results.mllm.verdict==='fake'?'#dc2626':results.mllm.verdict==='real'?'#16a34a':'#ca8a04'}">
              {{ results.mllm.verdict==='fake'?'判断：伪造':results.mllm.verdict==='real'?'判断：真实':'判断：不确定' }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 统计格子 -->
    <div class="stats-row">
      <div class="stat-box stat-main">
        <div class="stat-num">{{ doneCount }}/{{ modules.length }}</div>
        <div class="stat-label">检测项目</div>
      </div>
      <div class="stat-box" v-if="modules.includes('deepfake')">
        <div class="stat-num" :class="results.deepfake ? 'num-done' : currentStep==='deepfake' ? 'num-running' : 'num-idle'">
          {{ results.deepfake ? '完成' : currentStep==='deepfake' ? '运行中' : '—' }}
        </div>
        <div class="stat-label">Deepfake</div>
      </div>
      <div class="stat-box" v-if="modules.includes('mllm')">
        <div class="stat-num" :class="results.mllm ? 'num-done' : currentStep==='mllm' ? 'num-running' : 'num-idle'">
          {{ results.mllm ? '完成' : currentStep==='mllm' ? '运行中' : '—' }}
        </div>
        <div class="stat-label">MLLM分析</div>
      </div>
      <div class="stat-box" v-if="modules.includes('rag')">
        <div class="stat-num" :class="results.rag ? 'num-done' : currentStep==='rag' ? 'num-running' : 'num-idle'">
          {{ results.rag ? '完成' : currentStep==='rag' ? '运行中' : '—' }}
        </div>
        <div class="stat-label">RAG审核</div>
      </div>
      <div class="stat-box">
        <div class="stat-num" :class="loading ? 'num-running' : 'num-done'">{{ loading ? '运行中' : '就绪' }}</div>
        <div class="stat-label">系统状态</div>
      </div>
    </div>

    <!-- 检测中扫描动画覆盖层 -->
    <div v-if="loading" class="scan-overlay">
      <div class="scan-box">
        <div class="scan-line"></div>
        <div class="scan-text">{{ currentStep ? `正在运行 ${currentStep.toUpperCase()}...` : '初始化检测...' }}</div>
      </div>
    </div>

    <!-- 上传 + 检测 -->
    <div class="action-row">
      <el-upload drag accept="image/*" :auto-upload="false"
        :on-change="onFileChange" :show-file-list="false" class="upload-zone">
        <div class="upload-inner">
          <!-- 上传区插画 -->
          <svg width="80" height="80" viewBox="0 0 80 80" fill="none" class="upload-illustration">
            <circle cx="40" cy="40" r="36" fill="#fdf2f8" stroke="#f9a8d4" stroke-width="1.5"/>
            <circle cx="40" cy="40" r="26" fill="none" stroke="#f472b6" stroke-width="1" stroke-dasharray="4 3" opacity="0.5"/>
            <rect x="28" y="26" width="24" height="28" rx="3" fill="white" stroke="#f472b6" stroke-width="1.5"/>
            <line x1="33" y1="33" x2="47" y2="33" stroke="#f9a8d4" stroke-width="1.5" stroke-linecap="round"/>
            <line x1="33" y1="38" x2="47" y2="38" stroke="#f9a8d4" stroke-width="1.5" stroke-linecap="round"/>
            <line x1="33" y1="43" x2="41" y2="43" stroke="#f9a8d4" stroke-width="1.5" stroke-linecap="round"/>
            <path d="M40 52 L40 62 M36 58 L40 62 L44 58" stroke="#f472b6" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <div class="upload-text">拖拽或点击上传图像</div>
          <div class="upload-sub">支持 JPG / PNG / WebP</div>
        </div>
      </el-upload>
      <div style="display:flex;flex-direction:column;gap:8px;justify-content:center">
        <div style="font-size:12px;color:#94a3b8;margin-bottom:2px">选择检测模块</div>
        <label style="display:flex;align-items:center;gap:6px;font-size:13px;cursor:pointer">
          <input type="checkbox" v-model="modules" value="deepfake" /> Deepfake检测（需人脸）
        </label>
        <label style="display:flex;align-items:center;gap:6px;font-size:13px;cursor:pointer">
          <input type="checkbox" v-model="modules" value="mllm" /> MLLM可解释分析
        </label>
        <label style="display:flex;align-items:center;gap:6px;font-size:13px;cursor:pointer">
          <input type="checkbox" v-model="modules" value="rag" /> RAG内容审核
        </label>
        <button class="detect-btn" :disabled="(!file && !auditText.trim()) || loading || modules.length===0" @click="runAudit">
          <span v-if="loading" class="btn-spin"><LoaderIcon :size="16" /></span>
          <span>{{ loading ? '检测中...' : '开始检测' }}</span>
        </button>
      </div>
    </div>

    <!-- RAG 文本输入 -->
    <div class="card" style="padding:12px 16px">
      <div style="font-size:12px;color:#94a3b8;margin-bottom:6px">RAG 内容审核文本（可单独审核）</div>
      <div style="display:flex;gap:8px;align-items:flex-start">
        <textarea v-model="auditText" rows="2" placeholder="输入需要审核的文字内容..." style="flex:1;border:1px solid #fce7f3;border-radius:8px;padding:8px;font-size:13px;resize:vertical;outline:none"></textarea>
        <button class="send-btn" :disabled="!auditText.trim() || ragLoading" @click="runRagOnly" style="white-space:nowrap">
          {{ ragLoading ? '审核中...' : '文本审核' }}
        </button>
      </div>
      <div v-if="results.rag" style="margin-top:8px;font-size:12px">
        <span class="badge" :class="results.rag.safe?'badge-success':'badge-danger'">{{ results.rag.safe?'安全':'风险' }}</span>
        <span style="margin-left:8px;color:#64748b">风险等级: {{ results.rag.risk_level?.toUpperCase() }}</span>
        <span v-if="results.rag.matched_keywords?.length" style="margin-left:8px;color:#dc2626">命中: {{ results.rag.matched_keywords.join(', ') }}</span>
      </div>
    </div>

    <!-- 检测结果 -->
    <div v-if="results.deepfake || results.mllm || results.rag" class="results-grid">
      <div class="card result-card" v-if="results.deepfake"
           v-motion :initial="{opacity:0,y:20}" :enter="{opacity:1,y:0,transition:{duration:400}}">
        <div class="card-title">Deepfake 检测</div>
        <div class="result-body">
          <span class="badge" :class="results.deepfake.label === 'fake' ? 'badge-danger' : results.deepfake.label === 'skipped' ? 'badge-warn' : 'badge-success'">
            {{ results.deepfake.label === 'fake' ? '伪造' : results.deepfake.label === 'skipped' ? '非人脸' : '真实' }}
          </span>
          <span class="result-meta">置信度 {{ (results.deepfake.confidence * 100).toFixed(1) }}%</span>
        </div>
      </div>

      <div class="card result-card" v-if="results.mllm"
           v-motion :initial="{opacity:0,y:20}" :enter="{opacity:1,y:0,transition:{duration:400,delay:100}}">
        <div class="card-title">MLLM 可解释性</div>
        <div class="result-body">
          <span class="badge" :class="verdictClass(results.mllm.verdict)">
            {{ verdictLabel(results.mllm.verdict) }}
          </span>
          <p class="result-text">{{ results.mllm.explanation }}</p>
          <div v-if="results.mllm.evidence?.length" class="tags">
            <span v-for="e in results.mllm.evidence" :key="e" class="tag">{{ e }}</span>
          </div>
        </div>
      </div>

      <div class="card result-card" v-if="results.rag"
           v-motion :initial="{opacity:0,y:20}" :enter="{opacity:1,y:0,transition:{duration:400,delay:200}}">
        <div class="card-title">内容安全审核</div>
        <div class="result-body">
          <span class="badge" :class="results.rag.safe ? 'badge-success' : 'badge-danger'">
            {{ results.rag.safe ? '安全' : '风险' }}
          </span>
          <span class="result-meta">风险等级: {{ results.rag.risk_level?.toUpperCase() }}</span>
          <div v-if="results.rag.matched_keywords?.length" class="tags">
            <span v-for="k in results.rag.matched_keywords" :key="k" class="tag tag-danger">{{ k }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 一言卡片：仿 NapCat Hitokoto -->
    <div class="card quote-card">
      <QuoteIcon :size="36" class="quote-icon" />
      <div class="quote-text">" {{ quote.text }} "</div>
      <div class="quote-from">
        <span class="quote-source">—— {{ quote.from }}</span>
        <span class="quote-author">{{ quote.author }}</span>
      </div>
      <button class="quote-refresh" @click="refreshQuote" title="换一句">
        <RefreshIcon :size="14" />
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

// Inline SVG icons
const ImageIcon = { template: `<svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>`, props: ['size'] }
const UploadIcon = { template: `<svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/></svg>`, props: ['size'] }
const LoaderIcon = { template: `<svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin-anim"><line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="22"/><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"/><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"/><line x1="2" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="22" y2="12"/><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"/><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"/></svg>`, props: ['size'] }
const QuoteIcon = { template: `<svg :width="size" :height="size" viewBox="0 0 24 24" fill="currentColor"><path d="M3 21c3 0 7-1 7-8V5c0-1.25-.756-2.017-2-2H4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2 1 0 1 0 1 1v1c0 1-1 2-2 2s-1 .008-1 1.031V20c0 1 0 1 1 1z"/><path d="M15 21c3 0 7-1 7-8V5c0-1.25-.757-2.017-2-2h-4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2h.75c0 2.25.25 4-2.75 4v3c0 1 0 1 1 1z"/></svg>`, props: ['size'] }
const RefreshIcon = { template: `<svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>`, props: ['size'] }

const file = ref<File | null>(null)
const preview = ref('')
const loading = ref(false)
const results = reactive<Record<string, any>>({})
const mllmModel = ref('GPT-4o')
const auditText = ref('')
const modules = ref(['deepfake', 'mllm', 'rag'])
const currentStep = ref('')

onMounted(async () => {
  try {
    const r = await fetch('/api/system/info')
    const d = await r.json()
    mllmModel.value = d.mllm_model
  } catch {}
})

const doneCount = computed(() =>
  [results.deepfake, results.mllm, results.rag].filter(Boolean).length
)

const quotes = [
  { text: '凡是过往，皆为序章。', from: '暴风雨', author: '莎士比亚' },
  { text: '知识就是力量。', from: '新工具论', author: '培根' },
  { text: '科学没有国界，科学家有祖国。', from: '', author: '巴斯德' },
  { text: '技术是把双刃剑，关键在于使用它的人。', from: '', author: '比尔·盖茨' },
  { text: '人工智能是新的电力。', from: '', author: 'Andrew Ng' },
  { text: '我们必须确保AI的发展对全人类有益。', from: '', author: 'Demis Hassabis' },
  { text: '真相是最好的防御。', from: '', author: '爱德华·默罗' },
  { text: '在信息时代，隐私是一种奢侈品，也是一种权利。', from: '', author: '布鲁斯·施奈尔' },
  { text: '深度伪造技术的出现，让我们重新思考"眼见为实"。', from: '', author: '匿名' },
  { text: '安全不是产品，而是一个过程。', from: '', author: '布鲁斯·施奈尔' },
  { text: '数据是新时代的石油，但未经提炼的数据毫无价值。', from: '', author: 'Clive Humby' },
  { text: '最危险的谎言是接近真相的谎言。', from: '', author: '尼采' },
]
const quoteIdx = ref(Math.floor(Math.random() * quotes.length))
const quote = ref(quotes[quoteIdx.value])

const refreshQuote = async () => {
  // 先尝试一言 API
  try {
    const r = await fetch('https://v1.hitokoto.cn/?c=k&c=i&c=d', { signal: AbortSignal.timeout(3000) })
    const d = await r.json()
    quote.value = { text: d.hitokoto, from: d.from || '', author: d.from_who || '一言' }
    return
  } catch {}
  // fallback 本地随机
  const next = (quoteIdx.value + 1 + Math.floor(Math.random() * (quotes.length - 1))) % quotes.length
  quoteIdx.value = next
  quote.value = quotes[next]
}

const formatSize = (b: number) => {
  if (b < 1024) return b + ' B'
  if (b < 1048576) return (b / 1024).toFixed(1) + ' KB'
  return (b / 1048576).toFixed(1) + ' MB'
}

const verdictClass = (v: string) =>
  v === 'fake' ? 'badge-danger' : v === 'real' ? 'badge-success' : 'badge-warn'
const verdictLabel = (v: string) =>
  v === 'fake' ? '伪造' : v === 'real' ? '真实' : '不确定'

const onFileChange = (f: any) => {
  file.value = f.raw
  preview.value = URL.createObjectURL(f.raw)
}

const onTextInput = () => {
  if (auditText.value.trim() && !modules.value.includes('rag'))
    modules.value.push('rag')
}

const ragLoading = ref(false)

const runRagOnly = async () => {
  if (!auditText.value.trim() || ragLoading.value) return
  ragLoading.value = true
  try {
    const fd = new FormData()
    fd.append('text', auditText.value.trim())
    const r = await fetch('/api/detect/content', { method: 'POST', body: fd })
    results.rag = await r.json()
  } catch {
    ElMessage.error('审核失败')
  } finally {
    ragLoading.value = false
  }
}

const runAudit = async () => {
  if (!file.value && !auditText.value.trim()) { ElMessage.warning('请上传图像或输入文本'); return }
  loading.value = true
  Object.keys(results).forEach(k => delete results[k])

  const form = new FormData()
  if (file.value) form.append('image', file.value)
  if (auditText.value.trim()) form.append('text', auditText.value.trim())
  form.append('modules', modules.value.join(','))

  const resp = await fetch('/api/detect/full', { method: 'POST', body: form })
  const reader = resp.body!.getReader()
  const decoder = new TextDecoder()
  let buf = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const parts = buf.split('\n\n')
    buf = parts.pop() ?? ''
    for (const part of parts) {
      const lines = part.split('\n')
      const event = lines.find(l => l.startsWith('event:'))?.slice(7).trim()
      const data = lines.find(l => l.startsWith('data:'))?.slice(5).trim()
      if (!event || !data) continue
      const payload = JSON.parse(data)
      if (event === 'step') currentStep.value = payload.step
      if (event === 'deepfake') { results.deepfake = payload; currentStep.value = '' }
      if (event === 'mllm') { results.mllm = payload; currentStep.value = '' }
      if (event === 'rag') { results.rag = payload; currentStep.value = '' }
      if (event === 'done') {
        loading.value = false
        // 保存报告
        try {
          const fd = new FormData()
          if (file.value) fd.append('image', file.value)
          if (auditText.value.trim()) fd.append('text', auditText.value.trim())
          const rr = await fetch('/api/detect/report', { method: 'POST', body: fd })
          const rd = await rr.json()
          const ids = JSON.parse(localStorage.getItem('report_ids') || '[]')
          ids.push(rd.report_id)
          localStorage.setItem('report_ids', JSON.stringify(ids))
        } catch {}
      }
    }
  }
  loading.value = false
}
</script>

<style scoped>
.detect-page { max-width: 1100px; margin: 0 auto; display: flex; flex-direction: column; gap: 16px; }

.scan-overlay {
  position: fixed; top: 0; left: 0; width: 100%; height: 100%;
  background: rgba(255,245,249,0.7); backdrop-filter: blur(4px);
  z-index: 100; display: flex; align-items: center; justify-content: center;
}
.scan-box {
  width: 280px; height: 280px; border: 2px solid #f472b6;
  border-radius: 16px; position: relative; overflow: hidden;
  background: rgba(255,255,255,0.9);
  box-shadow: 0 0 40px rgba(244,114,182,0.3), inset 0 0 40px rgba(244,114,182,0.05);
}
.scan-line {
  position: absolute; left: 0; width: 100%; height: 3px;
  background: linear-gradient(90deg, transparent, #f472b6, transparent);
  animation: scan 2s linear infinite;
  box-shadow: 0 0 12px #f472b6;
}
@keyframes scan { 0% { top: 0 } 100% { top: 100% } }
.scan-text {
  position: absolute; bottom: 20px; width: 100%;
  text-align: center; font-size: 13px; color: #f472b6; font-weight: 600;
  animation: blink 1s ease-in-out infinite;
}
@keyframes blink { 0%,100% { opacity:1 } 50% { opacity:0.4 } }

/* Top grid */
.top-grid { display: grid; grid-template-columns: 260px 1fr 260px; gap: 14px; }

.info-card { display: flex; align-items: center; gap: 14px; }
.avatar-wrap { position: relative; flex-shrink: 0; }
.avatar-img { width: 56px; height: 56px; border-radius: 50%; object-fit: cover; box-shadow: 0 0 0 2px rgba(244,114,182,0.3); }
.avatar-placeholder { width: 56px; height: 56px; border-radius: 50%; background: #fdf2f8; display: flex; align-items: center; justify-content: center; color: #f9a8d4; }
.avatar-dot { position: absolute; right: 2px; bottom: 2px; width: 12px; height: 12px; border-radius: 50%; border: 2px solid #fff; }
.dot-ready { background: #22c55e; }
.dot-idle { background: #cbd5e1; }
.info-name { font-size: 15px; font-weight: 600; color: #1e293b; }
.info-sub { font-size: 12px; color: #94a3b8; margin-top: 2px; font-family: monospace; }

.sys-card {}
.sys-rows { display: flex; flex-direction: column; gap: 10px; }
.sys-row { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.sys-dot { width: 6px; height: 6px; border-radius: 50%; background: #f472b6; flex-shrink: 0; }
.sys-label { color: #64748b; flex: 1; }
.sys-val { color: #1e293b; font-weight: 500; font-size: 12px; }

.ring-card { display: flex; align-items: center; justify-content: center; }
.ring-wrap { display: flex; gap: 24px; }
.ring-item { display: flex; flex-direction: column; align-items: center; gap: 6px; }
.ring-svg { width: 88px; height: 88px; transform: rotate(-90deg); }
.ring-bg { fill: none; stroke: #fce7f3; stroke-width: 7; }
.ring-fill { fill: none; stroke-width: 7; stroke-linecap: round; stroke-dasharray: 239; transition: stroke-dashoffset 0.7s ease; }
.ring-pink { stroke: #f472b6; }
.ring-purple { stroke: #a855f7; }
.ring-center { position: absolute; display: flex; align-items: baseline; gap: 1px; }
.ring-item { position: relative; }
.ring-item .ring-center { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%) rotate(0deg); }
.ring-val { font-size: 20px; font-weight: 700; color: #f472b6; line-height: 1; }
.ring-val-purple { color: #a855f7; }
.ring-unit { font-size: 11px; font-weight: 600; color: #f472b6; }
.ring-label { font-size: 11px; color: #94a3b8; }

/* Stats row */
.stats-row { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; }
.stat-box { background: rgba(255,255,255,0.8); border: 1px solid #fce7f3; border-radius: 14px; padding: 14px 12px; text-align: center; backdrop-filter: blur(8px); }
.stat-main { border-color: #f9a8d4; background: rgba(253,242,248,0.8); }
.stat-num { font-size: 22px; font-weight: 700; color: #1e293b; }
.stat-label { font-size: 11px; color: #94a3b8; margin-top: 3px; }
.num-done { color: #22c55e; }
.num-idle { color: #cbd5e1; }
.num-running { color: #f59e0b; animation: pulse 1s infinite; }
@keyframes pulse { 0%,100% { opacity:1 } 50% { opacity:0.5 } }

/* Action row */
.action-row { display: flex; gap: 14px; }
.upload-zone { flex: 1; }
.upload-zone :deep(.el-upload-dragger) {
  background: rgba(255,255,255,0.7) !important;
  border: 2px dashed #fce7f3 !important;
  border-radius: 14px !important;
  padding: 24px !important;
  transition: border-color 0.2s !important;
}
.upload-zone :deep(.el-upload-dragger:hover) { border-color: #f9a8d4 !important; }
.upload-inner { display: flex; flex-direction: column; align-items: center; gap: 6px; }
.upload-icon { color: #f9a8d4; }
.upload-text { font-size: 14px; color: #64748b; font-weight: 500; }
.upload-sub { font-size: 12px; color: #cbd5e1; }

.detect-btn {
  width: 180px; border-radius: 14px; border: none;
  background: linear-gradient(135deg, #f472b6, #ec4899);
  color: #fff; font-size: 14px; font-weight: 600; cursor: pointer;
  display: flex; align-items: center; justify-content: center; gap: 8px;
  transition: opacity 0.2s, box-shadow 0.2s;
  box-shadow: 0 4px 14px rgba(244,114,182,0.35);
}
.detect-btn:hover:not(:disabled) { box-shadow: 0 6px 20px rgba(244,114,182,0.5); }
.detect-btn:disabled { opacity: 0.5; cursor: not-allowed; box-shadow: none; }
.btn-spin { display: flex; }
.btn-spin :deep(.spin-anim) { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* Results */
.results-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
.result-card {}
.result-body { display: flex; flex-direction: column; gap: 8px; }
.badge { display: inline-flex; align-items: center; padding: 3px 12px; border-radius: 9999px; font-size: 12px; font-weight: 600; width: fit-content; }
.badge-success { background: #dcfce7; color: #16a34a; }
.badge-danger { background: #fee2e2; color: #dc2626; }
.badge-warn { background: #fef3c7; color: #ca8a04; }
.result-meta { font-size: 12px; color: #64748b; }
.result-text { font-size: 13px; color: #475569; line-height: 1.6; }
.tags { display: flex; flex-wrap: wrap; gap: 5px; }
.tag { padding: 2px 8px; border-radius: 6px; font-size: 11px; background: #fdf2f8; color: #f472b6; border: 1px solid #fce7f3; }
.tag-danger { background: #fee2e2; color: #dc2626; border-color: #fecaca; }

/* Quote */
.quote-card { position: relative; text-align: center; padding: 28px 32px; }
.quote-icon { color: rgba(244,114,182,0.2); margin: 0 auto 12px; display: block; }
.quote-text { font-size: 17px; color: #1e293b; font-weight: 500; line-height: 1.7; margin-bottom: 12px; font-style: italic; }
.quote-from { display: flex; flex-direction: column; gap: 2px; }
.quote-source { color: #f472b6; font-size: 13px; font-weight: 600; }
.quote-author { color: #94a3b8; font-size: 12px; }
.quote-refresh {
  position: absolute; top: 16px; right: 16px;
  background: none; border: none; cursor: pointer;
  color: #cbd5e1; padding: 6px; border-radius: 9999px;
  transition: all 0.18s; display: flex;
}
.quote-refresh:hover { background: #fdf2f8; color: #f472b6; }
</style>
