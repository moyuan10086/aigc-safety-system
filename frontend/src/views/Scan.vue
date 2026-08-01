<template>
  <div class="page">
    <div class="card">
      <div class="card-title">LLM 漏洞扫描 (garak)</div>
      <div class="preset-row">
        <label>扫描预设</label>
        <div class="preset-btns">
          <button v-for="p in presets" :key="p.value"
            :class="['preset-btn', { active: preset === p.value }]"
            @click="preset = p.value">{{ p.label }}</button>
        </div>
      </div>
      <div class="preset-desc">{{ presetDesc }}</div>
      <button class="scan-btn" :disabled="scanning" @click="startScan">
        <span v-if="!scanning">开始扫描</span>
        <span v-else>扫描中...</span>
      </button>
    </div>

    <div class="card log-card" v-if="logs.length">
      <div class="card-title">
        扫描日志
        <span v-if="done" class="status-badge ok">完成</span>
      </div>
      <div class="log-box" ref="logBox">
        <div v-for="(line, i) in logs" :key="i" class="log-line">{{ line }}</div>
      </div>
    </div>

    <div class="card" v-if="results.length">
      <div class="card-title">扫描结果</div>
      <table class="result-table">
        <thead><tr><th>探针</th><th>通过</th><th>失败</th><th>错误</th><th>通过率</th></tr></thead>
        <tbody>
          <tr v-for="r in results" :key="r.name">
            <td>{{ r.name }}</td>
            <td class="num-pass">{{ r.passed }}</td>
            <td class="num-fail">{{ r.failed }}</td>
            <td>{{ r.errors }}</td>
            <td>{{ r.total ? ((r.passed/r.total)*100).toFixed(0)+'%' : '-' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import { ElMessage } from 'element-plus'

const preset = ref('quick')
const scanning = ref(false)
const done = ref(false)
const logs = ref<string[]>([])
const results = ref<any[]>([])
const logBox = ref<HTMLElement | null>(null)

const presets = [
  { value: 'quick', label: '快速' },
  { value: 'standard', label: '标准' },
  { value: 'full', label: '完整' },
]

const presetDescs: Record<string, string> = {
  quick: '3个探针：Bullying、SexualContent、SlurUsage',
  standard: '6个探针：lmrc 完整套件',
  full: '8个探针：lmrc + DAN越狱 + Base64注入',
}
const presetDesc = computed(() => presetDescs[preset.value])

async function startScan() {
  scanning.value = true
  done.value = false
  logs.value = []
  results.value = []

  const es = new EventSource(`/api/garak/scan?preset=${preset.value}`)
  es.onmessage = async (e) => {
    const msg = JSON.parse(e.data)
    if (msg.type === 'start') {
      logs.value.push(`[开始] 探针: ${msg.probes.join(', ')}`)
    } else if (msg.type === 'probe') {
      logs.value.push(`[运行] ${msg.name} (${msg.total} prompts)`)
    } else if (msg.type === 'result') {
      const s = msg.failed === 0 ? '✅' : '⚠️'
      logs.value.push(`${s} ${msg.name}: 通过${msg.passed} 失败${msg.failed} 错误${msg.errors}`)
      results.value.push(msg)
    } else if (msg.type === 'error') {
      logs.value.push(`❌ ${msg.name}: ${msg.msg}`)
    } else if (msg.type === 'done') {
      done.value = true
      scanning.value = false
      es.close()
    }
    await nextTick()
    if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight
  }
  es.onerror = () => { scanning.value = false; done.value = true; es.close() }
}
</script>

<style scoped>
.page { max-width: 800px; margin: 0 auto; display: flex; flex-direction: column; gap: 16px; }
.preset-row { display: flex; align-items: center; gap: 12px; margin-bottom: 6px; }
.preset-row label { font-size: 12px; color: #64748b; font-weight: 500; white-space: nowrap; }
.preset-btns { display: flex; gap: 8px; }
.preset-btn {
  padding: 6px 16px; border-radius: 9999px; border: 1px solid #fce7f3;
  background: #fff; font-size: 13px; color: #64748b; cursor: pointer;
  transition: all 0.18s;
}
.preset-btn.active { background: linear-gradient(135deg,#f472b6,#ec4899); color:#fff; border-color:transparent; }
.preset-desc { font-size: 12px; color: #94a3b8; margin-bottom: 12px; }
.scan-btn {
  padding: 9px 28px; border-radius: 9999px; border: none;
  background: linear-gradient(135deg,#f472b6,#ec4899);
  color: #fff; font-size: 13px; font-weight: 600; cursor: pointer;
  transition: opacity 0.2s;
}
.scan-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.scan-btn:not(:disabled):hover { opacity: 0.85; }
.log-card { padding-bottom: 0; }
.log-box {
  background: #0f172a; border-radius: 10px; padding: 12px 14px;
  max-height: 420px; overflow-y: auto; margin-top: 8px;
}
.log-line { font-family: monospace; font-size: 12px; color: #94a3b8; line-height: 1.6; white-space: pre-wrap; word-break: break-all; }
.result-table { width:100%; border-collapse:collapse; font-size:13px; margin-top:8px; }
.result-table th { text-align:left; padding:6px 10px; color:#94a3b8; font-weight:600; font-size:11px; border-bottom:1px solid #fce7f3; }
.result-table td { padding:8px 10px; border-bottom:1px solid #fce7f3; color:#1e293b; }
.num-pass { color:#16a34a; font-weight:600; }
.num-fail { color:#dc2626; font-weight:600; }
</style>
