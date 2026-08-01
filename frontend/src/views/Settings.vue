<template>
  <div class="page">
    <div class="card">
      <div class="card-title">系统设置</div>
      <div class="form">
        <div class="field">
          <label>MLLM API Base URL</label>
          <input v-model="form.baseUrl" placeholder="https://api.openai.com/v1" />
        </div>
        <div class="field">
          <label>MLLM 模型</label>
          <input v-model="form.model" placeholder="gpt-4o" />
        </div>
        <div class="field">
          <label>API Key</label>
          <input v-model="form.apiKey" type="password" placeholder="sk-..." />
        </div>
        <div class="field">
          <label>Deepfake 模型路径</label>
          <input v-model="form.modelPath" placeholder="../deepfake-detection/weights/model.torchscript" />
        </div>
        <div class="field">
          <label>ChromaDB 路径</label>
          <input v-model="form.chromaPath" placeholder="./rag_db" />
        </div>
        <div class="field">
          <label>敏感词库路径</label>
          <input v-model="form.lexiconPath" placeholder="../Sensitive-lexicon/Vocabulary" />
        </div>
      </div>
      <div class="actions">
        <button class="save-btn" @click="save">保存配置</button>
      </div>
    </div>

    <div class="card" style="margin-top:16px">
      <div class="card-title">关于系统</div>
      <div class="about-rows">
        <div class="about-row"><span class="k">系统名称</span><span class="v">AIGC内容安全检测系统</span></div>
        <div class="about-row"><span class="k">版本</span><span class="v">1.0.0</span></div>
        <div class="about-row"><span class="k">Deepfake模型</span><span class="v">CLIP-ViT-L/14 + LN-tuning</span></div>
        <div class="about-row"><span class="k">后端框架</span><span class="v">FastAPI + SSE</span></div>
        <div class="about-row"><span class="k">前端框架</span><span class="v">Vue 3 + Element Plus</span></div>
        <div class="about-row"><span class="k">RAG引擎</span><span class="v">ChromaDB + SentenceTransformers</span></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

const form = reactive({
  baseUrl: '',
  model: '',
  apiKey: '',
  modelPath: '',
  chromaPath: '',
  lexiconPath: '',
})

onMounted(async () => {
  try {
    const res = await fetch('/api/system/info')
    const data = await res.json()
    form.baseUrl = data.mllm_base_url
    form.model = data.mllm_model
    form.modelPath = data.deepfake_model_path
    form.chromaPath = data.chroma_path
    form.lexiconPath = data.lexicon_path
  } catch {
    ElMessage.error('无法读取后端配置')
  }
})

const save = async () => {
  try {
    await fetch('/api/system/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mllm_base_url: form.baseUrl,
        mllm_model: form.model,
        mllm_api_key: form.apiKey,
        deepfake_model_path: form.modelPath,
        chroma_path: form.chromaPath,
        lexicon_path: form.lexiconPath,
      })
    })
    ElMessage.success('配置已保存')
  } catch {
    ElMessage.error('保存失败')
  }
}
</script>

<style scoped>
.page { max-width: 800px; margin: 0 auto; display: flex; flex-direction: column; gap: 0; }
.form { display: flex; flex-direction: column; gap: 14px; }
.field { display: flex; flex-direction: column; gap: 5px; }
.field label { font-size: 12px; color: var(--muted); font-weight: 500; }
.field input {
  padding: 9px 12px; border-radius: 5px;
  border: 1px solid var(--line); background: #0b1218;
  font-size: 13px; color: var(--text); outline: none;
  transition: border-color 0.18s;
}
.field input:focus { border-color: var(--primary); }
.actions { margin-top: 16px; }
.save-btn {
  padding: 9px 24px; border-radius: 5px; border: none;
  background: var(--primary); color: #06110f; font-size: 13px; font-weight: 700;
  cursor: pointer; transition: opacity 0.2s;
}
.save-btn:hover { opacity: 0.85; }
.about-rows { display: flex; flex-direction: column; gap: 0; }
.about-row { display: flex; align-items: center; gap: 12px; font-size: 13px; padding: 9px 0; border-bottom: 1px solid var(--line); }
.about-row:last-child { border-bottom: none; }
.k { color: var(--muted); width: 120px; flex-shrink: 0; }
.v { color: var(--text); font-weight: 500; }
</style>
