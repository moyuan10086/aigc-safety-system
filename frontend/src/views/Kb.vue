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
        <span style="font-size:11px;color:#94a3b8;padding:1px 8px;background:#f1f5f9;border-radius:9999px">{{ f.category }}</span>
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
        </div>
      </div>
      <div class="input-row">
        <input v-model="question" class="q-input" placeholder="输入问题..." @keyup.enter="sendQuestion" />
        <button class="send-btn" :disabled="asking" @click="sendQuestion">发送</button>
      </div>
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
const messages = ref<{role:string,content:string}[]>([])
const question = ref('')
const asking = ref(false)
const chatBox = ref<HTMLElement>()
const category = ref('默认')
const filterCategory = ref('')

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
  messages.value.push({ role: 'assistant', content: '' })
  const idx = messages.value.length - 1

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
  border: 2px dashed #fce7f3; border-radius: 12px; padding: 32px;
  text-align: center; cursor: pointer; color: #94a3b8; font-size: 14px;
  transition: border-color 0.2s;
}
.upload-area:hover { border-color: #f472b6; color: #f472b6; }
.refresh-btn { margin-left: auto; font-size: 12px; padding: 2px 10px; border-radius: 9999px; border: 1px solid #fce7f3; background: none; cursor: pointer; color: #f472b6; }
.empty { color: #94a3b8; font-size: 13px; padding: 12px 0; }
.file-row { display: flex; align-items: center; padding: 8px 0; border-bottom: 1px solid #fce7f3; gap: 12px; }
.file-name { flex: 1; font-size: 13px; cursor: pointer; color: #1e293b; }
.file-name:hover { color: #f472b6; }
.del-btn { font-size: 12px; padding: 2px 10px; border-radius: 9999px; border: 1px solid #fce7f3; background: none; cursor: pointer; color: #ef4444; }
.chunk-row { display: flex; gap: 10px; padding: 6px 0; border-bottom: 1px solid #fce7f3; font-size: 12px; }
.chunk-idx { color: #f472b6; font-weight: 600; width: 28px; flex-shrink: 0; }
.chunk-text { color: #475569; line-height: 1.5; white-space: pre-wrap; word-break: break-all; }
.chat-box { min-height: 120px; max-height: 300px; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
.msg { max-width: 80%; padding: 8px 12px; border-radius: 12px; font-size: 13px; line-height: 1.6; white-space: pre-wrap; word-break: break-word; }
.msg.user { align-self: flex-end; background: #fdf2f8; color: #1e293b; }
.msg.assistant { align-self: flex-start; background: #f8fafc; color: #1e293b; }
.input-row { display: flex; gap: 8px; }
.q-input { flex: 1; padding: 8px 14px; border-radius: 9999px; border: 1px solid #fce7f3; font-size: 13px; outline: none; }
.q-input:focus { border-color: #f472b6; }
.send-btn { padding: 8px 20px; border-radius: 9999px; border: none; background: #f472b6; color: #fff; font-size: 13px; cursor: pointer; }
.send-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
