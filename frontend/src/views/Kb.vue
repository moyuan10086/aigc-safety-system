<template>
  <div class="page">
    <!-- 上传区 -->
    <div class="card">
      <div class="card-title">上传文件</div>
      <div style="display:flex;gap:8px;margin-bottom:8px">
        <select v-model="category" class="q-input" style="max-width:220px">
          <option value="默认">默认</option>
          <option value="法规政策">法规政策</option>
          <option value="技术文档">技术文档</option>
          <option value="案例分析">案例分析</option>
          <option value="安全规范">安全规范</option>
        </select>
        <input v-model="category" class="q-input" placeholder="或自定义分类..." style="max-width:160px" />
      </div>
      <div class="upload-area" @click="fileInput.click()" @dragover.prevent @drop.prevent="onDrop">
        <input ref="fileInput" type="file" accept=".txt,.pdf,.docx" style="display:none" @change="onFileChange" />
        <span v-if="!uploading">拖拽或点击上传（TXT / PDF / DOCX）</span>
        <span v-else>上传中...</span>
      </div>
    </div>

    <!-- 文件列表 -->
    <div class="card" style="margin-top:16px">
      <div class="card-title">已上传文件
        <input v-model="filterCategory" class="q-input" placeholder="按分类过滤..." style="max-width:150px;margin-left:8px;font-weight:400" @input="loadFiles" />
        <button class="refresh-btn" @click="loadFiles">刷新</button>
      </div>
      <div v-if="files.length === 0" class="empty">暂无文件</div>
      <div v-for="f in files" :key="f.file_id" class="file-row">
        <span class="file-name" @click="loadChunks(f)">{{ f.filename }}</span>
        <span class="category-tag">{{ f.category }}</span>
        <button class="del-btn" @click="deleteFile(f.file_id)">删除</button>
      </div>
    </div>

    <!-- 分块列表 -->
    <div v-if="chunks.length" class="card" style="margin-top:16px">
      <div class="card-title">分块内容 — {{ selectedFile?.filename }}</div>
      <div v-for="c in chunks" :key="c.chunk_id" class="chunk-row">
        <span class="chunk-idx">#{{ c.chunk_index }}</span>
        <span class="chunk-text">{{ c.content }}</span>
      </div>
    </div>

    <!-- 问答 -->
    <div class="card" style="margin-top:16px">
      <div class="card-title">知识库问答</div>
      <div class="chat-box" ref="chatBox">
        <div v-for="(m, i) in messages" :key="i" :class="['msg', m.role]">
          <span>{{ m.content }}</span>
          <div v-if="m.role === 'assistant' && m.sources?.length" class="answer-sources">
            <b>参考证据</b>
            <button v-for="source in m.sources" :key="source.chunk_id" type="button" @click="selectedSource = source">
              [{{ source.rank }}] {{ source.filename }} · #{{ source.chunk_index }}
            </button>
          </div>
        </div>
      </div>
      <div class="input-row">
        <input v-model="question" class="q-input" placeholder="输入问题..." @keyup.enter="sendQuestion" />
        <button class="send-btn" :disabled="asking" @click="sendQuestion">发送</button>
      </div>
    </div>
    <div v-if="selectedSource" class="source-drawer card">
      <div class="card-title">引用证据 [{{ selectedSource.rank }}]<button class="refresh-btn" @click="selectedSource = null">关闭</button></div>
      <p><b>{{ selectedSource.filename }}</b> · {{ selectedSource.category }} · 分块 #{{ selectedSource.chunk_index }}</p>
      <div class="source-score">融合 {{ Math.round(selectedSource.score * 100) }}% · 向量 {{ Math.round(selectedSource.vector_score * 100) }}% · 词法 {{ Math.round(selectedSource.keyword_score * 100) }}%</div>
      <pre>{{ selectedSource.snippet }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { toast } from 'vue3-toastify'

const API = '/api/kb'
const files = ref<any[]>([])
const chunks = ref<any[]>([])
const selectedFile = ref<any>(null)
const uploading = ref(false)
const fileInput = ref<HTMLInputElement>()
const messages = ref<{role:string,content:string,sources?:any[]}[]>([])
const question = ref('')
const asking = ref(false)
const chatBox = ref<HTMLElement>()
const category = ref('默认')
const filterCategory = ref('')
const selectedSource = ref<any>(null)

onMounted(loadFiles)

async function loadFiles() {
  const url = filterCategory.value ? `${API}/files?category=${encodeURIComponent(filterCategory.value)}` : `${API}/files`
  const r = await fetch(url)
  files.value = await r.json()
}

async function loadChunks(f: any) {
  selectedFile.value = f
  const r = await fetch(`${API}/files/${f.file_id}/chunks`)
  chunks.value = await r.json()
}

async function deleteFile(id: string) {
  await fetch(`${API}/files/${id}`, { method: 'DELETE' })
  chunks.value = []
  selectedFile.value = null
  loadFiles()
}

function onDrop(e: DragEvent) {
  const file = e.dataTransfer?.files[0]
  if (file) uploadFile(file)
}

function onFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) uploadFile(file)
}

async function uploadFile(file: File) {
  uploading.value = true
  const fd = new FormData()
  fd.append('file', file)
  fd.append('category', category.value || '默认')
  try {
    const r = await fetch(API + '/files', { method: 'POST', body: fd })
    const d = await r.json()
    toast.success(`上传成功：${d.filename}，共 ${d.chunks} 个分块`)
    loadFiles()
  } catch {
    toast.error('上传失败，请重试')
  } finally {
    uploading.value = false
  }
}

async function sendQuestion() {
  if (!question.value.trim() || asking.value) return
  messages.value.push({ role: 'user', content: question.value })
  const q = question.value
  question.value = ''
  asking.value = true
  messages.value.push({ role: 'assistant', content: '', sources: [] })
  const idx = messages.value.length - 1

  try {
    const searchBody = new FormData()
    searchBody.append('question', q)
    searchBody.append('top_k', '3')
    const searchResponse = await fetch(API + '/search', { method: 'POST', body: searchBody })
    if (searchResponse.ok) messages.value[idx].sources = (await searchResponse.json()).hits || []
  } catch {}

  const fd = new FormData()
  fd.append('question', q)
  const resp = await fetch(API + '/chat', { method: 'POST', body: fd })
  const reader = resp.body!.getReader()
  const dec = new TextDecoder()
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const text = dec.decode(value)
    for (const line of text.split('\n')) {
      if (line.startsWith('data: ')) {
        const d = line.slice(6)
        if (d === '[DONE]') break
        messages.value[idx].content += d
        await nextTick()
        chatBox.value?.scrollTo(0, chatBox.value.scrollHeight)
      }
    }
  }
  asking.value = false
}
</script>

<style scoped>
.page { max-width: 860px; margin: 0 auto; }
.upload-area {
  border: 1px dashed var(--line-bright); border-radius: 6px; padding: 32px;
  text-align: center; cursor: pointer; color: var(--muted); font-size: 13px;
  transition: border-color 0.2s;
}
.upload-area:hover { border-color: var(--primary); color: var(--primary); }
.refresh-btn { margin-left: auto; font-size: 11px; padding: 4px 9px; border-radius: 4px; border: 1px solid var(--line); background: none; cursor: pointer; color: var(--primary); }
.empty { color: var(--muted); font-size: 13px; padding: 12px 0; }
.file-row { display: flex; align-items: center; padding: 9px 0; border-bottom: 1px solid var(--line); gap: 12px; }
.file-name { flex: 1; font-size: 13px; cursor: pointer; color: var(--text); }
.file-name:hover { color: var(--primary); }
.category-tag{font-size:10px;color:var(--cyan);padding:3px 8px;background:rgba(56,189,248,.08);border:1px solid rgba(56,189,248,.18);border-radius:4px}
.del-btn { font-size: 11px; padding: 4px 9px; border-radius: 4px; border: 1px solid rgba(251,113,133,.25); background: none; cursor: pointer; color: var(--danger); }
.chunk-row { display: flex; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--line); font-size: 12px; }
.chunk-idx { color: var(--primary); font-weight: 600; width: 28px; flex-shrink: 0; }
.chunk-text { color: var(--muted); line-height: 1.5; white-space: pre-wrap; word-break: break-all; }
.chat-box { min-height: 120px; max-height: 300px; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
.msg { max-width: 80%; padding: 8px 12px; border-radius: 6px; font-size: 13px; line-height: 1.6; white-space: pre-wrap; word-break: break-word; }
.msg.user { align-self: flex-end; background: rgba(45,212,191,.1); color: var(--text); }
.msg.assistant { align-self: flex-start; background: #0b1218; color: var(--text); border:1px solid var(--line); }
.input-row { display: flex; gap: 8px; }
.q-input { flex: 1; padding: 8px 12px; border-radius: 5px; border: 1px solid var(--line); background:#0b1218; color:var(--text); font-size: 13px; outline: none; }
.q-input:focus { border-color: var(--primary); }
.send-btn { padding: 8px 20px; border-radius: 5px; border: none; background: var(--primary); color: #06110f; font-size: 13px; font-weight:700; cursor: pointer; }
.send-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.upload-area{background:var(--surface-2)}
.refresh-btn,.del-btn{background:#fff}
.category-tag{color:var(--cyan);background:rgba(22,140,168,.08);border-color:rgba(22,140,168,.2)}
.msg.user{background:rgba(8,126,174,.09)}
.msg.assistant,.q-input{background:var(--surface-2)}
.send-btn{color:#fff}
.answer-sources{display:flex;flex-wrap:wrap;gap:5px;margin-top:9px;padding-top:8px;border-top:1px solid var(--line)}
.answer-sources b{width:100%;color:var(--muted);font-size:10px}
.answer-sources button{padding:4px 7px;border:1px solid var(--line);border-radius:4px;background:var(--surface);color:var(--primary);font-size:10px;cursor:pointer}
.source-drawer{margin-top:16px}.source-drawer .card-title{display:flex;justify-content:space-between}.source-drawer p{color:var(--muted);font-size:11px}.source-score{margin-bottom:9px;color:var(--primary);font-size:10px}.source-drawer pre{max-height:280px;overflow:auto;margin:0;padding:12px;border-radius:5px;background:var(--surface-2);color:var(--text);font:11px/1.65 ui-monospace,monospace;white-space:pre-wrap}
</style>
