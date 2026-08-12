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
    <div v-if="stats" class="report-stats">
      <div class="stat-item"><div class="stat-num">{{ stats.total }}</div><div class="stat-label">全部报告</div></div>
      <div class="stat-item danger"><div class="stat-num">{{ stats.fake_count }}</div><div class="stat-label">真实性风险</div></div>
      <div class="stat-item warning"><div class="stat-num">{{ stats.risk_count }}</div><div class="stat-label">内容风险或待复核</div></div>
      <div class="stat-item success"><div class="stat-num">{{ stats.clear_count }}</div><div class="stat-label">已完成且未命中风险</div></div>
    </div>
    <div class="report-toolbar">
      <label class="report-search"><Search :size="15" /><input v-model.trim="filters.keyword" placeholder="搜索文件名或报告 ID" /></label>
      <select v-model="filters.type" aria-label="检测类型筛选"><option value="">全部类型</option><option value="provenance">AI 来源验证</option><option value="authenticity">真实性检测</option><option value="content_safety">视觉内容安全</option><option value="rag">红线知识库</option><option value="combined">组合检测</option></select>
      <select v-model="filters.risk" aria-label="风险状态筛选"><option value="">全部状态</option><option value="risk">风险或待复核</option><option value="clear">未命中风险</option><option value="unknown">结论不足</option></select>
      <select v-model="filters.sort" aria-label="报告排序"><option value="newest">最新优先</option><option value="oldest">最早优先</option><option value="filename">按文件名</option></select>
      <button class="toolbar-reset" type="button" @click="resetFilters" title="清空筛选"><RotateCcw :size="15" /></button>
    </div>
    <div class="selection-bar">
      <label><input type="checkbox" :checked="allVisibleSelected" @change="toggleAllVisible" />选择当前结果</label>
      <span>显示 {{ filteredReports.length }} / {{ reports.length }} 份</span>
      <button v-if="selectedIds.size" type="button" :disabled="deleting" @click="deleteSelected"><Trash2 :size="14" />删除所选（{{ selectedIds.size }}）</button>
    </div>

    <div v-if="loading" class="card" style="text-align:center;padding:32px;color:#94a3b8">
      加载报告中...
    </div>
    <div v-else-if="reports.length === 0" class="card">
      <el-empty description="暂无报告，请前往图像检测页面进行检测" />
    </div>
    <div v-if="!loading && filteredReports.length === 0" class="card filtered-empty">没有符合筛选条件的报告</div>
    <article v-for="r in filteredReports" :key="r.id" class="report-card" :class="{ selected: selectedIds.has(r.id) }">
      <label class="report-select" title="选择报告"><input type="checkbox" :checked="selectedIds.has(r.id)" @change="toggleSelected(r.id)" /></label>
      <div v-if="r.thumbnail?.url" class="report-thumb">
        <button type="button" @click="previewImage = r.thumbnail.url" title="查看样本缩略图">
          <img :src="r.thumbnail.url" :alt="`${r.filename || '审核样本'} 缩略图`" loading="lazy" />
        </button>
        <small>审核缩略图<br />非原始证据</small>
      </div>
      <header class="report-head">
        <div class="report-identity">
          <span class="report-type">{{ reportKind(r) }}</span>
          <h2>{{ r.report_title || reportTitle(r) }}</h2>
          <div class="sample-line"><FileImage v-if="r.filename" :size="14" /><span>{{ r.filename || '文本审核任务' }}</span><time>{{ formatTime(r.created_at) }}</time></div>
        </div>
        <div class="report-actions">
          <button @click="copyId(r.id)" title="复制报告 ID"><Copy :size="15" /></button>
          <a :href="`/api/detect/report/${r.id}/download`" title="下载 JSON"><Braces :size="15" /></a>
          <a :href="`/api/detect/report/${r.id}/download/md`" title="下载 Markdown"><Download :size="15" /></a>
          <button class="danger-action" type="button" @click="deleteOne(r)" title="删除报告"><Trash2 :size="15" /></button>
        </div>
      </header>

      <div class="scope-row"><span>检测范围</span><b v-for="module in reportModules(r)" :key="module">{{ moduleLabel(module) }}</b></div>

      <!-- 检测结果摘要 -->
      <div class="report-grid">
        <div v-if="shouldShow(r, 'provenance') && r.provenance" class="result-block provenance-block">
          <div class="section-label">AI 来源与内容凭证</div>
          <span class="badge" :class="provenanceClass(r.provenance.overall_state)">{{ provenanceLabel(r.provenance.overall_state) }}</span>
          <p>{{ provenanceNote(r.provenance.overall_state) }}</p>
        </div>
        <div v-if="shouldShow(r, 'deepfake') && r.deepfake" class="result-block">
          <div class="section-label">人脸伪造检测</div>
          <span class="badge" :class="r.deepfake.label==='fake'?'badge-danger':r.deepfake.label==='skipped'?'badge-warn':'badge-success'">
            {{ r.deepfake.label==='fake'?'伪造':r.deepfake.label==='skipped'?'非人脸':'真实' }}
          </span>
          <span style="font-size:12px;color:#64748b;margin-left:8px">得分 {{ (r.deepfake.score*100).toFixed(1) }}%</span>
        </div>
        <div v-if="shouldShow(r, 'mllm') && r.mllm" class="result-block">
          <div class="section-label">多模态真实性解释</div>
          <span class="badge" :class="r.mllm.verdict==='fake'?'badge-danger':r.mllm.verdict==='real'?'badge-success':'badge-warn'">
            {{ r.mllm.verdict==='fake'?'伪造':r.mllm.verdict==='real'?'真实':'不确定' }}
          </span>
        </div>
        <div v-if="shouldShow(r, 'rag') && r.rag" class="result-block">
          <div class="section-label">知识库检索增强审核</div>
          <span class="badge" :class="r.rag.safe?'badge-success':'badge-danger'">{{ r.rag.safe?'安全':'风险' }}</span>
          <span style="font-size:12px;color:#64748b;margin-left:8px">{{ r.rag.risk_level?.toUpperCase() }}</span>
        </div>
        <div v-if="shouldShow(r, 'content_safety') && r.content_safety" class="result-block">
          <div class="section-label">视觉内容安全</div>
          <span class="badge" :class="contentSafetyClass(r.content_safety.verdict)">{{ contentSafetyLabel(r.content_safety.verdict) }}</span>
          <span style="font-size:12px;color:#64748b;margin-left:8px">风险 {{ formatPercent(r.content_safety.risk_score) }}</span>
          <span v-if="r.content_safety.categories?.length" class="category-summary">{{ categorySummary(r.content_safety.categories) }}</span>
        </div>
      </div>

      <!-- MLLM 综合分析（Markdown 渲染） -->
      <details v-if="r.summary" class="markdown-report">
        <summary><span>查看分析说明</span><small>仅包含本次检测范围</small></summary>
        <div class="md-body" v-html="renderMd(r.summary)" />
      </details>
      <footer class="report-foot"><code>{{ r.id }}</code><span>报告字段仅代表已运行模块，未运行能力不作结论</span></footer>
    </article>
    <div v-if="previewImage" class="image-lightbox" role="dialog" aria-modal="true" @click.self="previewImage = ''">
      <button type="button" class="lightbox-close" @click="previewImage = ''" title="关闭预览">×</button>
      <img :src="previewImage" alt="审核样本预览" />
      <p>仅用于人工复核展示，不代表原始取证文件</p>
    </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { useClipboard } from '@vueuse/core'
import { toast } from 'vue3-toastify'
import { ElMessageBox } from 'element-plus'
import { Braces, Copy, Download, FileImage, FileText, RotateCcw, Search, ShieldCheck, Trash2 } from 'lucide-vue-next'
import AuditLogPanel from '../components/audit/AuditLogPanel.vue'
import { useAuth } from '../composables/useAuth'

const { copy } = useClipboard()
const activeView = ref<'reports' | 'logs'>('reports')

const reports = ref<any[]>([])
const stats = ref<any>(null)
const loading = ref(false)
const reportsLoaded = ref(false)
const previewImage = ref('')
const selectedIds = reactive(new Set<string>())
const deleting = ref(false)
const filters = reactive({ keyword:'', type:'', risk:'', sort:'newest' })
const { user } = useAuth()

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
const filteredReports = computed(() => {
  const keyword = filters.keyword.toLowerCase()
  const items = reports.value.filter(report => {
    if (keyword && !`${report.filename || ''} ${report.id || ''} ${report.report_title || ''}`.toLowerCase().includes(keyword)) return false
    if (filters.type && reportTypeCode(report) !== filters.type) return false
    if (filters.risk && reportRiskState(report) !== filters.risk) return false
    return true
  })
  return items.sort((a,b) => filters.sort === 'oldest' ? String(a.created_at).localeCompare(String(b.created_at)) : filters.sort === 'filename' ? String(a.filename || '').localeCompare(String(b.filename || ''), 'zh-CN') : String(b.created_at).localeCompare(String(a.created_at)))
})
const allVisibleSelected = computed(() => filteredReports.value.length > 0 && filteredReports.value.every(report => selectedIds.has(report.id)))
function reportTypeCode(report:any) { const modules=reportModules(report); if(modules.length>1)return 'combined'; if(modules.includes('provenance'))return 'provenance'; if(modules.includes('content_safety'))return 'content_safety'; if(modules.includes('rag'))return 'rag'; return 'authenticity' }
function reportRiskState(report:any) { if(report.deepfake?.label==='fake'||report.mllm?.verdict==='fake'||report.content_safety?.verdict==='unsafe'||report.content_safety?.verdict==='review'||report.rag?.safe===false||report.provenance?.overall_state==='invalid_or_tampered')return 'risk'; if(report.provenance?.overall_state==='inconclusive'||report.mllm?.verdict==='uncertain')return 'unknown'; return 'clear' }
function resetFilters(){Object.assign(filters,{keyword:'',type:'',risk:'',sort:'newest'})}
function toggleSelected(id:string){selectedIds.has(id)?selectedIds.delete(id):selectedIds.add(id)}
function toggleAllVisible(){if(allVisibleSelected.value)filteredReports.value.forEach(r=>selectedIds.delete(r.id));else filteredReports.value.forEach(r=>selectedIds.add(r.id))}
function openLogin(){window.dispatchEvent(new CustomEvent('aigc:open-login'))}
async function requestDelete(ids:string[]){
  if(!user.value){openLogin();toast.info('请先登录审核员账号');return}
  deleting.value=true
  try{
    for(const id of ids){const response=await fetch(`/api/detect/report/${id}`,{method:'DELETE',credentials:'same-origin'});if(!response.ok){const body=await response.json().catch(()=>({}));throw new Error(body.detail||'报告删除失败')}}
    reports.value=reports.value.filter(item=>!ids.includes(item.id));ids.forEach(id=>selectedIds.delete(id));reportsLoaded.value=false;await loadReports();toast.success(`已删除 ${ids.length} 份报告`)
  }catch(error){toast.error(error instanceof Error?error.message:'报告删除失败')}finally{deleting.value=false}
}
async function deleteOne(report:any){try{await ElMessageBox.confirm(`删除“${report.filename||report.report_title||report.id}”及其审核缩略图？此操作不可恢复。`,'删除检测报告',{type:'warning',confirmButtonText:'删除',cancelButtonText:'取消'});await requestDelete([report.id])}catch(error){if(error!=='cancel'&&error!=='close')toast.error('无法删除报告')}}
async function deleteSelected(){try{await ElMessageBox.confirm(`确认删除选中的 ${selectedIds.size} 份报告及其缩略图？此操作不可恢复。`,'批量删除报告',{type:'warning',confirmButtonText:'删除所选',cancelButtonText:'取消'});await requestDelete([...selectedIds])}catch(error){if(error!=='cancel'&&error!=='close')toast.error('无法删除报告')}}
function contentSafetyClass(verdict: string) { return verdict === 'unsafe' ? 'badge-danger' : verdict === 'safe' ? 'badge-success' : 'badge-warn' }
function contentSafetyLabel(verdict: string) { return ({ safe: '安全', review: '人工复核', unsafe: '阻断' } as Record<string, string>)[verdict] || '结论不足' }
function formatPercent(value: unknown) { const score = Number(value); return Number.isFinite(score) ? `${(score * 100).toFixed(1)}%` : '未知' }
function categorySummary(items: any[]) { return items.slice(0, 3).map(item => `${item.label || item.code} ${formatPercent(item.confidence)}`).join(' · ') }
const knownModules = ['provenance', 'face', 'deepfake', 'mllm', 'content_safety', 'rag']
function reportModules(report: any): string[] {
  return Array.isArray(report.requested_modules) && report.requested_modules.length
    ? report.requested_modules
    : knownModules.filter(key => report[key] != null)
}
function shouldShow(report: any, module: string) { return reportModules(report).includes(module) }
function moduleLabel(module: string) { return ({ provenance:'AI 来源验证', face:'人脸检测', deepfake:'人脸伪造', mllm:'真实性解释', content_safety:'视觉内容安全', rag:'红线知识库' } as Record<string,string>)[module] || module }
function reportTitle(report: any) {
  const modules = new Set(reportModules(report))
  if (modules.size === 1 && modules.has('provenance')) return 'AI 来源与内容凭证验证报告'
  if ([...modules].every(item => ['face','deepfake','mllm'].includes(item))) return '图像真实性检测报告'
  if (modules.size === 1 && modules.has('content_safety')) return '视觉内容安全审核报告'
  if (modules.size === 1 && modules.has('rag')) return '红线知识库审核报告'
  return '多维图片安全审核报告'
}
function reportKind(report: any) { return reportModules(report).length === 1 ? '专项检测' : '组合检测' }
function formatTime(value: string) { return value ? value.slice(0,19).replace('T',' ') : '时间未记录' }
function provenanceClass(state: string) { return state === 'confirmed_source' ? 'badge-success' : state === 'invalid_or_tampered' ? 'badge-danger' : 'badge-warn' }
function provenanceLabel(state: string) { return ({ confirmed_source:'来源凭证已确认', not_found:'未发现来源凭证', inconclusive:'证据不足', invalid_or_tampered:'凭证无效或疑似篡改' } as Record<string,string>)[state] || '状态未知' }
function provenanceNote(state: string) { return state === 'not_found' ? '未发现 C2PA 或平台来源标记，不能据此判断图片不是 AI 生成。' : state === 'confirmed_source' ? '来源声明与当前文件绑定验证通过；该结果不代表内容安全。' : state === 'invalid_or_tampered' ? '来源声明验证失败，需要结合原始文件和人工取证复核。' : '现有来源证据不足，无法形成确定结论。' }
</script>

<style scoped>
.report-page{width:100%;max-width:1500px;margin:0 auto}.report-list{max-width:1120px;margin:0 auto}.view-switcher{display:flex;align-items:flex-end;gap:18px;margin-bottom:18px}.view-switcher p{margin:0 0 5px;color:var(--primary);font:700 9px/1 ui-monospace,monospace}.view-switcher h1{margin:0;font-size:20px}.segmented{margin-left:auto;display:flex;padding:3px;background:var(--surface);border:1px solid var(--line);border-radius:7px;box-shadow:var(--shadow-sm)}.segmented button{height:32px;display:flex;align-items:center;gap:7px;padding:0 12px;color:var(--muted);background:transparent;border:0;border-radius:5px;font-size:11px;cursor:pointer}.segmented button.active{color:#fff;background:var(--primary);font-weight:650}.report-stats{display:grid;grid-template-columns:repeat(4,1fr);margin-bottom:18px;overflow:hidden;border:1px solid var(--line);border-radius:7px;background:var(--surface);box-shadow:var(--shadow-sm)}
.stat-item{position:relative;padding:18px 20px;border-right:1px solid var(--line)}.stat-item:last-child{border-right:0}.stat-item:before{content:"";position:absolute;left:0;top:17px;bottom:17px;width:3px;background:var(--primary)}.stat-item.danger:before{background:var(--danger)}.stat-item.warning:before{background:var(--warning)}.stat-item.success:before{background:var(--success)}.stat-num{font-size:24px;font-weight:700;color:var(--text)}.stat-label{margin-top:3px;color:var(--muted);font-size:11px}.report-card{margin-bottom:16px;padding:20px 22px;border:1px solid var(--line);border-radius:7px;background:var(--surface);box-shadow:var(--shadow-sm)}.report-head{display:flex;justify-content:space-between;align-items:flex-start;gap:18px}.report-type{color:var(--primary);font-size:10px;font-weight:700}.report-identity h2{margin:5px 0 7px;color:var(--text);font-size:18px;font-weight:700}.sample-line{display:flex;align-items:center;gap:7px;color:var(--muted);font-size:11px}.sample-line time{margin-left:9px;padding-left:16px;border-left:1px solid var(--line)}.report-actions{display:flex;gap:6px}.report-actions a,.report-actions button{width:32px;height:32px;display:grid;place-items:center;color:var(--muted);background:var(--surface-2);border:1px solid var(--line);border-radius:5px;cursor:pointer}.report-actions a:hover,.report-actions button:hover{color:var(--primary);border-color:var(--primary)}.scope-row{display:flex;align-items:center;flex-wrap:wrap;gap:7px;margin:17px 0 4px;padding:10px 12px;background:var(--surface-2);border-radius:5px}.scope-row>span{margin-right:5px;color:var(--muted);font-size:10px}.scope-row b{padding:3px 7px;color:var(--text);background:var(--surface);border:1px solid var(--line);border-radius:3px;font-size:10px;font-weight:600}.report-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:12px}.result-block{min-width:0;padding:13px 14px;border:1px solid var(--line);border-radius:5px;background:var(--surface-2)}.result-block p{margin:8px 0 0;color:var(--muted);font-size:11px;line-height:1.6}.provenance-block{grid-column:1/-1}
.badge { display:inline-flex;padding:3px 9px;border-radius:4px;font-size:11px;font-weight:600 }
.badge-success { background:rgba(52,211,153,.1);color:var(--success) }
.badge-danger { background:rgba(251,113,133,.1);color:var(--danger) }
.badge-warn { background:rgba(245,158,11,.1);color:var(--warning) }
.markdown-report{margin-top:14px;border-top:1px solid var(--line)}.markdown-report summary{display:flex;align-items:center;justify-content:space-between;padding:13px 2px;color:var(--text);font-size:12px;font-weight:650;cursor:pointer}.markdown-report summary small{color:var(--muted);font-size:10px;font-weight:400}.md-body{padding:2px 4px 12px;overflow-wrap:anywhere;color:var(--muted);font-size:12px;line-height:1.75}.report-foot{display:flex;align-items:center;justify-content:space-between;gap:14px;padding-top:12px;border-top:1px solid var(--line);color:var(--muted);font-size:10px}.report-foot code{max-width:45%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.category-summary{display:block;margin-top:6px;color:var(--muted);font-size:11px;line-height:1.5}
.md-body :deep(h1),.md-body :deep(h2),.md-body :deep(h3) { font-weight:700;margin:12px 0 6px;color:var(--text) }
.md-body :deep(h2) { font-size:14px }
.md-body :deep(h3) { font-size:13px }
.md-body :deep(ul),.md-body :deep(ol) { padding-left:20px;margin:6px 0 }
.md-body :deep(li) { margin:3px 0 }
.md-body :deep(strong) { color:var(--text) }
.md-body :deep(p) { margin:6px 0 }
.md-body :deep(a){color:var(--primary);text-decoration:none}.md-body :deep(blockquote){margin:10px 0;padding:8px 12px;color:var(--muted);background:var(--surface-2);border-left:3px solid var(--primary)}.md-body :deep(hr){margin:14px 0;border:0;border-top:1px solid var(--line)}.md-body :deep(pre){max-width:100%;margin:10px 0;padding:12px;overflow:auto;color:var(--text);background:var(--surface-3);border:1px solid var(--line);border-radius:6px}.md-body :deep(code){padding:1px 5px;background:var(--surface-3);border-radius:3px;font:12px/1.6 ui-monospace,SFMono-Regular,Consolas,monospace}.md-body :deep(pre code){padding:0;background:transparent}.md-body :deep(table){width:100%;margin:10px 0;border-collapse:collapse;font-size:12px}.md-body :deep(th),.md-body :deep(td){padding:7px 9px;border:1px solid var(--line);text-align:left}.md-body :deep(th){color:var(--text);background:var(--surface-2)}
@media(max-width:720px){.view-switcher{align-items:flex-start;flex-direction:column}.segmented{width:100%;margin-left:0}.segmented button{flex:1;justify-content:center}.report-stats{grid-template-columns:repeat(2,1fr)}.stat-item:nth-child(2){border-right:0}.stat-item:nth-child(-n+2){border-bottom:1px solid var(--line)}.report-head{flex-direction:column}.report-actions{width:100%;justify-content:flex-end}.report-grid{grid-template-columns:1fr}.sample-line{align-items:flex-start;flex-wrap:wrap}.sample-line time{width:100%;margin-left:0;padding-left:0;border-left:0}.report-foot{align-items:flex-start;flex-direction:column}.report-foot code{max-width:100%}}
.report-card{position:relative}.report-card:has(.report-thumb){padding-left:154px}.report-thumb{position:absolute;left:20px;top:20px;width:112px}.report-thumb button{width:112px;height:86px;padding:0;overflow:hidden;background:var(--surface-2);border:1px solid var(--line);border-radius:5px;cursor:zoom-in}.report-thumb img{width:100%;height:100%;display:block;object-fit:cover}.report-thumb small{display:block;margin-top:6px;color:var(--muted);font-size:9px;line-height:1.4;text-align:center}.image-lightbox{position:fixed;inset:0;z-index:1200;display:grid;place-items:center;padding:44px;background:rgba(5,18,28,.78);backdrop-filter:blur(4px)}.image-lightbox img{max-width:min(920px,90vw);max-height:78vh;display:block;object-fit:contain;border:1px solid rgba(255,255,255,.22);border-radius:6px;box-shadow:0 20px 60px rgba(0,0,0,.38)}.image-lightbox p{position:absolute;bottom:16px;margin:0;color:#dbe7ef;font-size:11px}.lightbox-close{position:absolute;right:24px;top:20px;width:36px;height:36px;color:#fff;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.28);border-radius:5px;font-size:24px;cursor:pointer}@media(max-width:720px){.report-card:has(.report-thumb){padding-left:22px;padding-top:126px}.report-thumb{left:22px}.report-thumb small{position:absolute;left:122px;top:27px;width:100px;text-align:left}.image-lightbox{padding:18px}}
.report-toolbar{display:grid;grid-template-columns:minmax(250px,1fr) 150px 160px 130px 38px;gap:8px;margin-bottom:8px}.report-search{height:38px;display:flex;align-items:center;gap:8px;padding:0 11px;color:var(--muted);background:var(--surface);border:1px solid var(--line);border-radius:6px}.report-search:focus-within{color:var(--primary);border-color:var(--primary)}.report-search input{width:100%;border:0;outline:0;background:transparent;color:var(--text);font-size:11px}.report-toolbar select{height:38px;padding:0 9px;color:var(--muted);background:var(--surface);border:1px solid var(--line);border-radius:6px;font-size:11px}.toolbar-reset{display:grid;place-items:center;color:var(--muted);background:var(--surface);border:1px solid var(--line);border-radius:6px;cursor:pointer}.toolbar-reset:hover{color:var(--primary);border-color:var(--primary)}.selection-bar{height:34px;display:flex;align-items:center;gap:14px;margin-bottom:10px;color:var(--muted);font-size:10px}.selection-bar label{display:flex;align-items:center;gap:6px}.selection-bar button{margin-left:auto;display:flex;align-items:center;gap:6px;height:30px;padding:0 10px;color:var(--danger);background:rgba(207,63,79,.06);border:1px solid rgba(207,63,79,.22);border-radius:5px;cursor:pointer}.report-card.selected{border-color:rgba(8,126,174,.48);box-shadow:0 0 0 2px rgba(8,126,174,.08)}.report-select{position:absolute;right:22px;bottom:19px;z-index:2;width:18px;height:18px;display:grid;place-items:center}.report-select input{width:14px;height:14px}.danger-action:hover{color:var(--danger)!important;border-color:rgba(207,63,79,.4)!important}.filtered-empty{margin-bottom:16px;padding:36px;text-align:center;color:var(--muted);font-size:12px}@media(max-width:900px){.report-toolbar{grid-template-columns:1fr 1fr}.report-search{grid-column:1/-1}.toolbar-reset{height:38px}}@media(max-width:560px){.report-toolbar{grid-template-columns:1fr}.report-search{grid-column:auto}.selection-bar{flex-wrap:wrap;height:auto}.selection-bar button{width:100%;margin-left:0;justify-content:center}}
</style>
