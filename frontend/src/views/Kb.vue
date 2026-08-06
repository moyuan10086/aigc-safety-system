<template>
  <div class="kb-page">
    <header class="page-head">
      <div>
        <p>REDLINE INTELLIGENCE / RAG</p>
        <h1>红线知识库</h1>
        <span>汇集国家法规、内容安全基线与公开安全实践，为机器审核和人工复核提供可追溯证据。</span>
      </div>
      <div class="head-actions">
        <button class="icon-button" type="button" title="刷新知识库" :disabled="loading" @click="refreshAll"><RefreshCw :size="16" :class="{ spinning: loading }" /></button>
        <button class="command-button" type="button" @click="showUpload = true"><Upload :size="15" />导入资料</button>
      </div>
    </header>

    <section class="metric-grid" aria-label="知识库指标">
      <article class="metric-item"><span class="metric-icon"><LibraryBig :size="18" /></span><div><small>知识来源</small><strong>{{ stats.file_count || 0 }}</strong><p>官方 {{ stats.official_source_count || 0 }} · 用户 {{ stats.user_source_count || 0 }}</p></div></article>
      <article class="metric-item"><span class="metric-icon blue"><Blocks :size="18" /></span><div><small>证据分块</small><strong>{{ stats.chunk_count || 0 }}</strong><p>段落切分 · 重叠 {{ stats.chunk_overlap || 0 }} 字</p></div></article>
      <article class="metric-item"><span class="metric-icon green"><BadgeCheck :size="18" /></span><div><small>可信发布方</small><strong>{{ stats.publishers?.length || 0 }}</strong><p>政府 · 厂商 · 开源社区</p></div></article>
      <article class="metric-item"><span class="metric-icon amber"><ScanSearch :size="18" /></span><div><small>检索引擎</small><strong>混合</strong><p>语义 70% · 关键词 30%</p></div></article>
    </section>

    <nav class="category-tabs" aria-label="知识分类">
      <button v-for="item in categoryOptions" :key="item.value" type="button" :class="{ active: activeCategory === item.value }" @click="selectCategory(item.value)">
        <component :is="item.icon" :size="15" /><span>{{ item.label }}</span><b>{{ categoryCount(item.value) }}</b>
      </button>
    </nav>

    <div class="workspace-grid">
      <section class="source-panel">
        <div class="panel-toolbar">
          <div class="search-box"><Search :size="15" /><input v-model="sourceQuery" placeholder="搜索标题、发布方或摘要" /></div>
          <span>共 {{ filteredFiles.length }} 项</span>
        </div>

        <div v-if="loading" class="panel-state"><LoaderCircle :size="22" class="spinning" />正在同步知识来源</div>
        <div v-else-if="filteredFiles.length === 0" class="panel-state"><FolderSearch2 :size="24" />当前筛选下暂无资料</div>
        <div v-else class="source-list">
          <article v-for="source in filteredFiles" :key="source.file_id" class="source-row" @click="openSource(source)">
            <span class="source-mark" :class="categoryTone(source.category)"><component :is="categoryIcon(source.category)" :size="19" /></span>
            <div class="source-copy">
              <div class="source-title"><strong>{{ source.title || source.filename }}</strong><span v-if="source.managed"><BadgeCheck :size="13" />平台维护</span></div>
              <p>{{ source.summary || '用户上传的知识资料，可参与检索与问答。' }}</p>
              <div class="source-meta">
                <span>{{ source.publisher || '用户上传' }}</span><i></i><span>{{ documentTypeName(source.document_type) }}</span><i></i><span>{{ source.chunk_count || 0 }} 个分块</span><i></i><span>{{ source.category }}</span><template v-if="source.has_full_text"><i></i><span class="full-text">全文</span></template>
              </div>
            </div>
            <div class="row-actions">
              <a v-if="source.source_url" :href="source.source_url" target="_blank" rel="noopener" title="查看公开原文" @click.stop><ExternalLink :size="15" /></a>
              <button type="button" title="查看证据分块" @click.stop="openSource(source)"><ChevronRight :size="16" /></button>
              <button v-if="!source.managed" class="danger" type="button" title="删除用户资料" @click.stop="deleteFile(source)"><Trash2 :size="15" /></button>
            </div>
          </article>
        </div>
      </section>

      <aside class="qa-panel">
        <div class="qa-head">
          <span><Bot :size="18" /></span>
          <div><strong>安全知识问答</strong><small>回答必须引用当前知识库证据</small></div>
          <i></i>
        </div>
        <div ref="chatBox" class="chat-box">
          <div v-if="messages.length === 0" class="qa-empty">
            <ShieldQuestion :size="30" />
            <strong>从红线要求开始提问</strong>
            <p>系统会检索法规和安全实践，并给出可点击的证据引用。</p>
            <button v-for="prompt in examplePrompts" :key="prompt" type="button" @click="question = prompt; sendQuestion()">{{ prompt }}</button>
          </div>
          <div v-for="(message, index) in messages" :key="index" :class="['message', message.role]">
            <span>{{ message.content || (asking ? '正在检索证据并组织回答…' : '') }}</span>
            <div v-if="message.role === 'assistant' && message.sources?.length" class="citations">
              <b>引用证据</b>
              <button v-for="source in message.sources" :key="source.chunk_id" type="button" @click="selectedEvidence = source">
                [{{ source.rank }}] {{ source.filename }}<small>{{ source.publisher }}</small>
              </button>
            </div>
          </div>
        </div>
        <div class="question-box">
          <textarea v-model="question" rows="3" placeholder="例如：发现深度伪造人脸内容后，平台应如何处置？" @keydown.enter.exact.prevent="sendQuestion"></textarea>
          <div><span><LockKeyhole :size="12" />回答不替代最终人工判断</span><button type="button" :disabled="asking || !question.trim()" title="发送问题" @click="sendQuestion"><Send :size="16" /></button></div>
        </div>
      </aside>
    </div>

    <div v-if="showUpload" class="modal-mask" @click.self="showUpload = false">
      <section class="upload-dialog">
        <header><div><p>USER KNOWLEDGE</p><h2>导入用户资料</h2></div><button type="button" title="关闭" @click="showUpload = false"><X :size="18" /></button></header>
        <div class="upload-form">
          <label>资料分类<select v-model="uploadCategory"><option v-for="item in uploadCategories" :key="item" :value="item">{{ item }}</option></select></label>
          <label>自定义分类<input v-model="customCategory" placeholder="可选，例如：比赛材料" /></label>
        </div>
        <div class="upload-zone" @click="fileInput?.click()" @dragover.prevent @drop.prevent="onDrop">
          <input ref="fileInput" type="file" accept=".txt,.pdf,.docx" hidden @change="onFileChange" />
          <LoaderCircle v-if="uploading" :size="24" class="spinning" /><UploadCloud v-else :size="27" />
          <strong>{{ uploading ? '正在解析并向量化' : '拖拽或点击选择资料' }}</strong><span>支持 TXT、PDF、DOCX；上传内容仅作为用户资料，不冒充官方来源。</span>
        </div>
      </section>
    </div>

    <div v-if="selectedFile" class="drawer-mask" @click.self="closeSource">
      <aside class="source-drawer">
        <header><div><p>{{ selectedFile.category }} / {{ selectedFile.publisher }}</p><h2>{{ selectedFile.title || selectedFile.filename }}</h2></div><button type="button" title="关闭" @click="closeSource"><X :size="18" /></button></header>
        <div class="drawer-body">
          <div class="source-brief"><span :class="categoryTone(selectedFile.category)"><component :is="categoryIcon(selectedFile.category)" :size="21" /></span><div><strong>{{ selectedFile.summary || '用户上传资料' }}</strong><p>类型：{{ documentTypeName(selectedFile.document_type) }} · {{ selectedFile.chunk_count }} 个证据分块</p></div></div>
          <a v-if="selectedFile.source_url" class="origin-link" :href="selectedFile.source_url" target="_blank" rel="noopener"><ExternalLink :size="14" />查看发布方公开原文<span>最终解释以原始页面为准</span></a>
          <div class="boundary-note"><Info :size="15" /><p>知识检索结果是审核辅助证据。命中条目不代表内容已经违法，也不能直接替代模型检测和人工复核。</p></div>
          <h3>证据分块</h3>
          <div v-if="chunksLoading" class="panel-state"><LoaderCircle :size="20" class="spinning" />加载分块</div>
          <article v-for="chunk in chunks" :key="chunk.chunk_id" class="chunk-item"><span>#{{ Number(chunk.chunk_index) + 1 }}</span><p>{{ chunk.content }}</p></article>
        </div>
      </aside>
    </div>

    <div v-if="selectedEvidence" class="drawer-mask" @click.self="selectedEvidence = null">
      <aside class="source-drawer evidence-drawer">
        <header><div><p>ANSWER EVIDENCE / [{{ selectedEvidence.rank }}]</p><h2>{{ selectedEvidence.filename }}</h2></div><button type="button" title="关闭" @click="selectedEvidence = null"><X :size="18" /></button></header>
        <div class="drawer-body">
          <div class="score-grid"><div><span>融合分</span><strong>{{ percent(selectedEvidence.score) }}</strong></div><div><span>语义分</span><strong>{{ percent(selectedEvidence.vector_score) }}</strong></div><div><span>词法分</span><strong>{{ percent(selectedEvidence.keyword_score) }}</strong></div></div>
          <div class="evidence-meta"><span>{{ selectedEvidence.publisher }}</span><span>{{ selectedEvidence.category }}</span><span>分块 #{{ Number(selectedEvidence.chunk_index) + 1 }}</span></div>
          <a v-if="selectedEvidence.source_url" class="origin-link" :href="selectedEvidence.source_url" target="_blank" rel="noopener"><ExternalLink :size="14" />核验公开原文</a>
          <pre>{{ selectedEvidence.snippet }}</pre>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { BadgeCheck, Blocks, Bot, Building2, ChevronRight, ExternalLink, FileUser, FolderSearch2, Globe2, Info, Landmark, LibraryBig, LoaderCircle, LockKeyhole, RefreshCw, ScanSearch, Search, Send, ShieldCheck, ShieldQuestion, Trash2, Upload, UploadCloud, X } from 'lucide-vue-next'
import { toast } from 'vue3-toastify'

const API = '/api/kb'
const files = ref<any[]>([])
const stats = ref<any>({})
const chunks = ref<any[]>([])
const selectedFile = ref<any>(null)
const selectedEvidence = ref<any>(null)
const loading = ref(false)
const chunksLoading = ref(false)
const uploading = ref(false)
const showUpload = ref(false)
const fileInput = ref<HTMLInputElement>()
const messages = ref<{ role:string; content:string; sources?:any[] }[]>([])
const question = ref('')
const asking = ref(false)
const chatBox = ref<HTMLElement>()
const activeCategory = ref('')
const sourceQuery = ref('')
const uploadCategory = ref('用户资料')
const customCategory = ref('')

const categoryOptions = [
  { value:'', label:'全部来源', icon:LibraryBig },
  { value:'国家法规', label:'国家法规', icon:Landmark },
  { value:'内容安全', label:'内容安全', icon:ShieldCheck },
  { value:'腾讯云安全', label:'腾讯云安全', icon:Globe2 },
  { value:'360 安全', label:'360 安全', icon:ScanSearch },
  { value:'长亭安全', label:'长亭安全', icon:Building2 },
  { value:'用户资料', label:'用户资料', icon:FileUser },
]
const uploadCategories = ['用户资料', '法规政策', '技术文档', '案例分析', '安全规范']
const examplePrompts = ['AI 生成图片需要添加什么标识？', '人脸深度伪造内容应如何人工复核？', 'API 遭遇高频恶意请求时如何处置？']

const filteredFiles = computed(() => {
  const keyword = sourceQuery.value.trim().toLowerCase()
  return files.value.filter(item => {
    if (activeCategory.value && (activeCategory.value === '用户资料' ? item.source_type !== 'user_upload' : item.category !== activeCategory.value)) return false
    if (!keyword) return true
    return [item.title, item.filename, item.publisher, item.summary, item.category].some(value => String(value || '').toLowerCase().includes(keyword))
  })
})

onMounted(refreshAll)

async function refreshAll() {
  loading.value = true
  try {
    const [fileResponse, statsResponse] = await Promise.all([fetch(`${API}/files`), fetch(`${API}/stats`)])
    if (!fileResponse.ok || !statsResponse.ok) throw new Error('知识库接口不可用')
    files.value = await fileResponse.json()
    stats.value = await statsResponse.json()
  } catch (error:any) {
    toast.error(error?.message || '知识库加载失败')
  } finally { loading.value = false }
}

function selectCategory(value:string) { activeCategory.value = value }
function categoryCount(value:string) {
  if (!value) return files.value.length
  if (value === '用户资料') return files.value.filter(item => item.source_type === 'user_upload').length
  return files.value.filter(item => item.category === value).length
}
function categoryIcon(category:string) {
  return categoryOptions.find(item => item.value === category)?.icon || FileUser
}
function categoryTone(category:string) {
  return ({ '国家法规':'tone-red', '内容安全':'tone-blue', '腾讯云安全':'tone-cyan', '360 安全':'tone-green', '长亭安全':'tone-amber' } as Record<string,string>)[category] || 'tone-neutral'
}
function documentTypeName(type:string) {
  return ({ regulation:'法规', law:'法律', technical_standard:'技术文件', national_standard:'国家标准', standard_record:'标准记录', curated_guide:'审核指南', vendor_guide:'厂商指南', vendor_research:'安全研究', open_source:'开源项目', user_document:'用户资料' } as Record<string,string>)[type] || '知识资料'
}
function percent(value:number) { return `${Math.round(Number(value || 0) * 100)}%` }

async function openSource(source:any) {
  selectedFile.value = source
  chunks.value = []
  chunksLoading.value = true
  try {
    const response = await fetch(`${API}/files/${encodeURIComponent(source.file_id)}/chunks`)
    if (!response.ok) throw new Error()
    chunks.value = await response.json()
  } catch { toast.error('证据分块加载失败') }
  finally { chunksLoading.value = false }
}
function closeSource() { selectedFile.value = null; chunks.value = [] }

async function deleteFile(source:any) {
  if (!window.confirm(`确定删除用户资料“${source.title || source.filename}”吗？`)) return
  const response = await fetch(`${API}/files/${encodeURIComponent(source.file_id)}`, { method:'DELETE' })
  if (!response.ok) { toast.error('资料删除失败'); return }
  toast.success('用户资料已删除')
  await refreshAll()
}

function onDrop(event:DragEvent) { const file = event.dataTransfer?.files[0]; if (file) uploadFile(file) }
function onFileChange(event:Event) { const file = (event.target as HTMLInputElement).files?.[0]; if (file) uploadFile(file) }
async function uploadFile(file:File) {
  uploading.value = true
  const body = new FormData()
  body.append('file', file)
  body.append('category', customCategory.value.trim() || uploadCategory.value)
  try {
    const response = await fetch(`${API}/files`, { method:'POST', body })
    if (!response.ok) throw new Error('上传失败')
    const result = await response.json()
    toast.success(`已导入 ${result.filename}，生成 ${result.chunks} 个分块`)
    showUpload.value = false
    await refreshAll()
  } catch (error:any) { toast.error(error?.message || '上传失败') }
  finally { uploading.value = false; if (fileInput.value) fileInput.value.value = '' }
}

async function sendQuestion() {
  const prompt = question.value.trim()
  if (!prompt || asking.value) return
  messages.value.push({ role:'user', content:prompt })
  question.value = ''
  asking.value = true
  messages.value.push({ role:'assistant', content:'', sources:[] })
  const index = messages.value.length - 1
  try {
    const searchBody = new FormData()
    searchBody.append('question', prompt)
    searchBody.append('top_k', '4')
    if (activeCategory.value && activeCategory.value !== '用户资料') searchBody.append('category', activeCategory.value)
    const searchResponse = await fetch(`${API}/search`, { method:'POST', body:searchBody })
    if (searchResponse.ok) messages.value[index].sources = (await searchResponse.json()).hits || []

    const body = new FormData(); body.append('question', prompt)
    const response = await fetch(`${API}/chat`, { method:'POST', body })
    if (!response.ok || !response.body) throw new Error('问答服务不可用')
    const reader = response.body.getReader(); const decoder = new TextDecoder()
    while (true) {
      const { done, value } = await reader.read(); if (done) break
      for (const line of decoder.decode(value, { stream:true }).split('\n')) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6); if (data !== '[DONE]') messages.value[index].content += data
      }
      await nextTick(); chatBox.value?.scrollTo({ top:chatBox.value.scrollHeight, behavior:'smooth' })
    }
  } catch (error:any) {
    messages.value[index].content = `暂时无法完成回答：${error?.message || '服务异常'}`
  } finally { asking.value = false }
}
</script>

<style scoped>
.kb-page{width:100%;max-width:1480px;margin:0 auto}.page-head{display:flex;align-items:flex-end;gap:24px;margin-bottom:16px}.page-head>div:first-child{min-width:0}.page-head p,.upload-dialog header p,.source-drawer header p{margin:0 0 7px;color:var(--primary);font:700 9px/1 ui-monospace,monospace}.page-head h1{margin:0;color:var(--text);font-size:23px;letter-spacing:0}.page-head>div>span{display:block;max-width:780px;margin-top:8px;color:var(--muted);font-size:12px;line-height:1.6}.head-actions{display:flex;gap:8px;margin-left:auto}.icon-button,.command-button{height:36px;display:inline-flex;align-items:center;justify-content:center;border:1px solid var(--line);border-radius:6px;cursor:pointer}.icon-button{width:36px;color:var(--muted);background:var(--surface)}.command-button{gap:7px;padding:0 13px;color:#fff;background:var(--primary);border-color:var(--primary);font-size:11px;font-weight:650}.metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:13px}.metric-item{min-width:0;height:98px;display:flex;align-items:center;gap:13px;padding:15px;background:var(--surface);border:1px solid var(--line);border-radius:8px;box-shadow:var(--shadow-sm)}.metric-icon{width:38px;height:38px;display:grid;place-items:center;flex:0 0 38px;color:#b83246;background:#fff0f2;border-radius:6px}.metric-icon.blue{color:var(--primary);background:#edf7fb}.metric-icon.green{color:var(--success);background:#ecf8f3}.metric-icon.amber{color:var(--warning);background:#fff7e8}.metric-item div{min-width:0}.metric-item small{display:block;color:var(--muted);font-size:10px}.metric-item strong{display:block;margin-top:4px;color:var(--text);font-size:22px;line-height:1}.metric-item p{margin:7px 0 0;color:var(--faint);font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.category-tabs{min-height:46px;display:flex;align-items:center;gap:4px;padding:5px;margin-bottom:13px;overflow-x:auto;background:var(--surface);border:1px solid var(--line);border-radius:8px;box-shadow:var(--shadow-sm)}.category-tabs button{height:34px;display:flex;align-items:center;gap:7px;padding:0 10px;color:var(--muted);background:transparent;border:0;border-radius:5px;white-space:nowrap;cursor:pointer;font-size:10px}.category-tabs button b{min-width:18px;padding:2px 5px;color:var(--faint);background:var(--surface-3);border-radius:8px;font-size:8px}.category-tabs button.active{color:#fff;background:var(--primary);font-weight:650}.category-tabs button.active b{color:#fff;background:rgba(255,255,255,.18)}.workspace-grid{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(340px,.75fr);gap:13px;align-items:start}.source-panel,.qa-panel{background:var(--surface);border:1px solid var(--line);border-radius:8px;box-shadow:var(--shadow-sm)}.source-panel{min-height:555px}.panel-toolbar{height:54px;display:flex;align-items:center;gap:14px;padding:0 14px;border-bottom:1px solid var(--line)}.search-box{height:34px;max-width:420px;display:flex;align-items:center;flex:1;gap:8px;padding:0 10px;color:var(--faint);background:var(--surface-2);border:1px solid var(--line);border-radius:6px}.search-box input{min-width:0;flex:1;color:var(--text);background:transparent;border:0;outline:0;font-size:11px}.panel-toolbar>span{margin-left:auto;color:var(--faint);font-size:9px}.source-list{padding:0 14px}.source-row{min-height:91px;display:flex;align-items:center;gap:13px;padding:13px 2px;border-bottom:1px solid var(--line);cursor:pointer}.source-row:last-child{border-bottom:0}.source-row:hover .source-title strong{color:var(--primary)}.source-mark,.source-brief>span{width:40px;height:40px;display:grid;place-items:center;flex:0 0 40px;border-radius:6px}.tone-red{color:#b83246;background:#fff0f2}.tone-blue{color:#176b9e;background:#edf7fb}.tone-cyan{color:#087eae;background:#ebf8fb}.tone-green{color:#167f5e;background:#ecf8f3}.tone-amber{color:#a66410;background:#fff7e8}.tone-neutral{color:#657987;background:#f0f4f6}.source-copy{min-width:0;flex:1}.source-title{display:flex;align-items:center;gap:8px}.source-title strong{min-width:0;color:var(--text);font-size:12px;font-weight:650;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.source-title span{display:flex;align-items:center;gap:3px;padding:2px 5px;color:var(--success);background:rgba(22,128,94,.07);border-radius:3px;font-size:8px;white-space:nowrap}.source-copy>p{margin:6px 0;color:var(--muted);font-size:10px;line-height:1.55;display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical;overflow:hidden}.source-meta{display:flex;align-items:center;gap:6px;color:var(--faint);font-size:8px}.source-meta i{width:2px;height:2px;background:var(--line-bright);border-radius:50%}.row-actions{display:flex;align-items:center;gap:4px}.row-actions a,.row-actions button,.upload-dialog header button,.source-drawer header button{width:30px;height:30px;display:grid;place-items:center;color:var(--muted);background:transparent;border:1px solid transparent;border-radius:5px;cursor:pointer}.row-actions a:hover,.row-actions button:hover{color:var(--primary);background:var(--surface-3);border-color:var(--line)}.row-actions .danger:hover{color:var(--danger)}.panel-state{min-height:300px;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:10px;color:var(--faint);font-size:11px}.qa-panel{position:sticky;top:12px;overflow:hidden}.qa-head{height:62px;display:flex;align-items:center;gap:11px;padding:0 14px;border-bottom:1px solid var(--line)}.qa-head>span{width:34px;height:34px;display:grid;place-items:center;color:var(--primary);background:#edf7fb;border-radius:6px}.qa-head div{display:flex;flex-direction:column}.qa-head strong{color:var(--text);font-size:11px}.qa-head small{margin-top:3px;color:var(--faint);font-size:8px}.qa-head i{width:7px;height:7px;margin-left:auto;background:var(--success);border-radius:50%;box-shadow:0 0 7px rgba(22,128,94,.4)}.chat-box{height:395px;display:flex;flex-direction:column;gap:10px;padding:14px;overflow:auto;background:var(--surface-2)}.qa-empty{display:flex;align-items:center;flex-direction:column;padding:28px 10px;color:var(--faint);text-align:center}.qa-empty>strong{margin-top:11px;color:var(--text);font-size:12px}.qa-empty p{margin:7px 0 14px;font-size:9px;line-height:1.6}.qa-empty button{width:100%;margin-top:6px;padding:8px 9px;color:var(--muted);text-align:left;background:var(--surface);border:1px solid var(--line);border-radius:5px;cursor:pointer;font-size:9px}.qa-empty button:hover{color:var(--primary);border-color:var(--line-bright)}.message{max-width:88%;padding:9px 11px;color:var(--text);background:var(--surface);border:1px solid var(--line);border-radius:6px;font-size:10px;line-height:1.65;white-space:pre-wrap}.message.user{align-self:flex-end;color:#fff;background:var(--primary);border-color:var(--primary)}.citations{display:flex;flex-direction:column;gap:5px;margin-top:9px;padding-top:8px;border-top:1px solid var(--line)}.citations>b{color:var(--faint);font-size:8px}.citations button{display:flex;align-items:center;gap:5px;padding:6px;color:var(--primary);text-align:left;background:var(--surface-2);border:1px solid var(--line);border-radius:4px;cursor:pointer;font-size:8px}.citations small{margin-left:auto;color:var(--faint)}.question-box{padding:12px;border-top:1px solid var(--line)}.question-box textarea{width:100%;min-height:64px;padding:9px;resize:none;color:var(--text);background:var(--surface-2);border:1px solid var(--line);border-radius:5px;outline:none;font:10px/1.5 inherit}.question-box textarea:focus{border-color:var(--primary)}.question-box>div{display:flex;align-items:center;margin-top:7px}.question-box span{display:flex;align-items:center;gap:4px;color:var(--faint);font-size:8px}.question-box button{width:31px;height:31px;display:grid;place-items:center;margin-left:auto;color:#fff;background:var(--primary);border:0;border-radius:5px;cursor:pointer}.question-box button:disabled{opacity:.4;cursor:not-allowed}.modal-mask,.drawer-mask{position:fixed;inset:0;z-index:120;display:flex;align-items:center;justify-content:center;padding:20px;background:rgba(16,33,44,.36);backdrop-filter:blur(2px)}.upload-dialog{width:min(600px,100%);padding:20px;background:var(--surface);border:1px solid var(--line);border-radius:8px;box-shadow:0 18px 50px rgba(15,35,48,.18)}.upload-dialog header,.source-drawer header{display:flex;align-items:flex-start;gap:12px}.upload-dialog h2,.source-drawer h2{margin:0;color:var(--text);font-size:18px;letter-spacing:0}.upload-dialog header button,.source-drawer header button{margin-left:auto;border-color:var(--line)}.upload-form{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:19px 0 12px}.upload-form label{display:flex;flex-direction:column;gap:6px;color:var(--muted);font-size:10px}.upload-form select,.upload-form input{height:36px;padding:0 9px;color:var(--text);background:var(--surface-2);border:1px solid var(--line);border-radius:5px;outline:none}.upload-zone{height:175px;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:8px;color:var(--primary);background:var(--surface-2);border:1px dashed var(--line-bright);border-radius:6px;cursor:pointer}.upload-zone strong{color:var(--text);font-size:11px}.upload-zone span{max-width:400px;color:var(--faint);font-size:9px;text-align:center;line-height:1.5}.drawer-mask{justify-content:flex-end;padding:0}.source-drawer{width:min(590px,100%);height:100%;background:var(--surface);border-left:1px solid var(--line);box-shadow:-16px 0 45px rgba(15,35,48,.15)}.source-drawer>header{min-height:86px;padding:20px 22px;border-bottom:1px solid var(--line)}.source-drawer header>div{min-width:0}.source-drawer header h2{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.drawer-body{height:calc(100% - 86px);padding:18px 22px 36px;overflow:auto}.source-brief{display:flex;align-items:flex-start;gap:11px;padding:13px;background:var(--surface-2);border:1px solid var(--line);border-radius:6px}.source-brief strong{color:var(--text);font-size:11px;line-height:1.55}.source-brief p{margin:5px 0 0;color:var(--faint);font-size:9px}.origin-link{min-height:42px;display:flex;align-items:center;gap:7px;margin-top:10px;padding:0 12px;color:var(--primary);background:#edf7fb;border:1px solid #d4eaf3;border-radius:6px;text-decoration:none;font-size:10px}.origin-link span{margin-left:auto;color:var(--faint);font-size:8px}.boundary-note{display:flex;align-items:flex-start;gap:8px;margin-top:10px;padding:11px;color:var(--warning);background:#fff8e9;border:1px solid #f1dfb9;border-radius:6px}.boundary-note svg{flex:0 0 auto}.boundary-note p{margin:0;color:#7f642f;font-size:9px;line-height:1.6}.drawer-body h3{margin:20px 0 8px;color:var(--text);font-size:11px}.chunk-item{display:grid;grid-template-columns:34px 1fr;gap:9px;padding:12px 0;border-bottom:1px solid var(--line)}.chunk-item>span{color:var(--primary);font:9px ui-monospace,monospace}.chunk-item p{margin:0;color:var(--muted);font-size:10px;line-height:1.75;white-space:pre-wrap}.score-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.score-grid div{padding:12px;background:var(--surface-2);border:1px solid var(--line);border-radius:6px}.score-grid span{display:block;color:var(--faint);font-size:8px}.score-grid strong{display:block;margin-top:5px;color:var(--primary);font-size:18px}.evidence-meta{display:flex;flex-wrap:wrap;gap:6px;margin:11px 0}.evidence-meta span{padding:4px 7px;color:var(--muted);background:var(--surface-3);border-radius:4px;font-size:8px}.evidence-drawer pre{margin-top:12px;padding:14px;color:var(--text);background:var(--surface-2);border:1px solid var(--line);border-radius:6px;font:10px/1.8 ui-monospace,monospace;white-space:pre-wrap;word-break:break-word}.spinning{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}@media(max-width:1150px){.metric-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.workspace-grid{grid-template-columns:minmax(0,1fr) 360px}}@media(max-width:880px){.page-head{align-items:flex-start;flex-direction:column}.head-actions{margin-left:0}.workspace-grid{grid-template-columns:1fr}.qa-panel{position:static}.chat-box{height:330px}}@media(max-width:620px){.metric-grid{grid-template-columns:1fr 1fr}.metric-item{height:112px;align-items:flex-start}.source-row{align-items:flex-start}.source-copy>p{display:none}.source-meta{flex-wrap:wrap}.row-actions{flex-direction:column}.upload-form{grid-template-columns:1fr}.page-head h1{font-size:20px}.source-drawer{width:100%}}@media(max-width:420px){.metric-grid{grid-template-columns:1fr}.metric-item{height:92px;align-items:center}.page-head{margin-bottom:12px}.page-head>div>span{font-size:11px}}
.source-meta .full-text{color:var(--success);font-weight:650}
</style>
