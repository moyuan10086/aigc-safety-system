<template>
  <div class="detect-page">
    <title>图片与人脸审核 - 面向 AIGC 伪造的跨域泛化检测与可解释性防御平台</title>

    <section class="task-header">
      <div class="task-heading">
        <span class="task-heading-icon"><ScanSearch :size="22" /></span>
        <div>
          <span class="task-kicker">IMAGE REVIEW WORKSPACE</span>
          <h1>新建图片审核</h1>
          <p>上传待审样本，按业务需要选择真实性、内容安全与知识库审核。</p>
        </div>
      </div>
      <div class="workflow-steps" aria-label="审核流程">
        <div class="workflow-step" :class="{ active: !file, done: !!file }"><Upload :size="16" /><span><b>上传样本</b><small>{{ file ? file.name : '等待图片' }}</small></span></div>
        <div class="workflow-step" :class="{ active: !!file && !loading && !hasResults, done: loading || hasResults }"><SlidersHorizontal :size="16" /><span><b>选择范围</b><small>{{ modules.length }} 项能力</small></span></div>
        <div class="workflow-step" :class="{ active: loading, done: hasResults }"><Play :size="16" /><span><b>执行检测</b><small>{{ loading ? '正在分析' : hasResults ? '检测完成' : '尚未开始' }}</small></span></div>
        <div class="workflow-step" :class="{ active: hasResults }"><UserCheck :size="16" /><span><b>人工复核</b><small>{{ hasResults ? '核对证据' : '等待结果' }}</small></span></div>
      </div>
    </section>

    <!-- 统计格子 -->
    <div v-if="file || loading || hasResults" class="stats-row">
      <div class="stat-box" v-if="modules.includes('deepfake')">
        <div class="stat-num" :class="results.deepfake ? 'num-done' : moduleIsRunning('deepfake') ? 'num-running' : 'num-idle'">
          {{ results.deepfake ? '完成' : moduleIsRunning('deepfake') ? '运行中' : '—' }}
        </div>
        <div class="stat-label">Deepfake</div>
      </div>
      <div class="stat-box" v-if="modules.includes('mllm')">
        <div class="stat-num" :class="results.mllm ? 'num-done' : moduleIsRunning('mllm') ? 'num-running' : 'num-idle'">
          {{ results.mllm ? '完成' : moduleIsRunning('mllm') ? '运行中' : '—' }}
        </div>
        <div class="stat-label">MLLM分析</div>
      </div>
      <div class="stat-box" v-if="modules.includes('rag')">
        <div class="stat-num" :class="results.rag ? 'num-done' : moduleIsRunning('rag') ? 'num-running' : 'num-idle'">
          {{ results.rag ? '完成' : moduleIsRunning('rag') ? '运行中' : '—' }}
        </div>
        <div class="stat-label">知识库审核</div>
      </div>
      <div class="stat-box" v-if="modules.includes('content_safety')">
        <div class="stat-num" :class="results.content_safety ? 'num-done' : moduleIsRunning('content_safety') ? 'num-running' : 'num-idle'">
          {{ results.content_safety ? '完成' : moduleIsRunning('content_safety') ? '运行中' : '—' }}
        </div>
        <div class="stat-label">图片内容安全</div>
      </div>
    </div>

    <!-- 检测中扫描动画覆盖层 -->
    <div v-if="loading" class="scan-overlay">
      <div class="scan-box">
        <div class="scan-line"></div>
        <div class="scan-text">{{ currentStepLabel }}</div>
        <div class="scan-meta">已用时 {{ loadingElapsed }} 秒 · 可继续等待或取消</div>
        <button class="scan-cancel" type="button" @click="cancelAudit">取消检测</button>
      </div>
    </div>

    <!-- 上传 + 检测 -->
    <div class="action-row">
      <el-upload drag accept="image/*" :auto-upload="false"
        :on-change="onFileChange" :show-file-list="false" class="upload-zone">
        <div class="upload-inner">
          <img v-if="preview" :src="preview" class="upload-preview" alt="待审核图片预览" />
          <svg v-else width="80" height="80" viewBox="0 0 80 80" fill="none" class="upload-illustration">
            <circle cx="40" cy="40" r="36" fill="#eef4f8" stroke="#b7c6d3" stroke-width="1.5"/>
            <circle cx="40" cy="40" r="26" fill="none" stroke="#087eae" stroke-width="1" stroke-dasharray="4 3" opacity="0.55"/>
            <rect x="28" y="26" width="24" height="28" rx="3" fill="#ffffff" stroke="#087eae" stroke-width="1.5"/>
            <line x1="33" y1="33" x2="47" y2="33" stroke="#b7c6d3" stroke-width="1.5" stroke-linecap="round"/>
            <line x1="33" y1="38" x2="47" y2="38" stroke="#b7c6d3" stroke-width="1.5" stroke-linecap="round"/>
            <line x1="33" y1="43" x2="41" y2="43" stroke="#b7c6d3" stroke-width="1.5" stroke-linecap="round"/>
            <path d="M40 52 L40 62 M36 58 L40 62 L44 58" stroke="#087eae" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <div class="upload-text">{{ file ? file.name : '拖拽或点击上传图像' }}</div>
          <div class="upload-sub">{{ file ? `${formatSize(file.size)} · 点击可更换样本` : '支持 JPG / PNG / WebP' }}</div>
        </div>
      </el-upload>
      <div class="control-panel">
        <div class="module-heading"><span>检测范围</span><small>{{ modules.length }}/4 个模块</small></div>
        <div class="module-group"><b>真实性检测</b>
          <label class="module-option"><input type="checkbox" v-model="modules" value="deepfake" /><span>Deepfake 人脸伪造</span><small>需检测到人脸</small></label>
          <label class="module-option"><input type="checkbox" v-model="modules" value="mllm" /><span>MLLM 解释分析</span><small>给出可读证据</small></label>
        </div>
        <div class="module-group"><b>内容与合规</b>
          <label class="module-option"><input type="checkbox" v-model="modules" value="rag" /><span>红线知识库审核（RAG）</span><small>规则与语义证据</small></label>
          <label class="module-option"><input type="checkbox" v-model="modules" value="content_safety" /><span>图片内容安全</span><small>敏感类别识别</small></label>
        </div>
        <label class="audit-note-field"><span>审计备注（可选）</span><textarea v-model="auditEvidenceNote" maxlength="500" rows="2" placeholder="例如：比赛现场人工复核样本"></textarea><small>{{ auditEvidenceNote.length }}/500 · 请勿填写密码或密钥</small></label>
        <div class="module-actions">
        <button class="source-btn" :disabled="!file || provenanceLoading" @click="runProvenance">
          {{ provenanceLoading ? '验证中...' : '验证 AI 来源' }}
        </button>
        <button class="source-btn" :disabled="!file || watermarkLoading" @click="generateAuditWatermark">
          {{ watermarkLoading ? '生成中...' : '生成门限审计包' }}
        </button>
        <button class="source-btn" :disabled="auditPackageLoading" @click="selectAuditPackage">
          {{ auditPackageLoading ? '核验中...' : '导入门限审计包' }}
        </button>
        <input ref="auditPackageInput" class="visually-hidden" type="file" accept=".zip,application/zip" @change="verifyAuditPackage" />
        <button class="source-btn" :disabled="!file || invisibleWatermarkLoading" @click="generateInvisibleWatermark">
          {{ invisibleWatermarkLoading ? '嵌入中...' : '生成隐形标识图' }}
        </button>
        <button class="detect-btn" :disabled="(!file && !auditText.trim()) || loading || modules.length===0 || (modules.includes('rag') && ocrLoading)" @click="runAudit">
          <span v-if="loading" class="btn-spin"><LoaderIcon :size="16" /></span>
          <span>{{ loading ? '检测中...' : '开始检测' }}</span>
        </button>
        </div>
      </div>
    </div>

    <section v-if="file" class="ocr-review" aria-labelledby="ocr-review-title">
      <header class="ocr-review-head">
        <span>
          <small>OCR · RAG INPUT</small>
          <b id="ocr-review-title">图片文字识别与校对</b>
        </span>
        <em class="ocr-status" :class="`ocr-status-${ocrStatus}`">{{ ocrStatusLabel }}</em>
      </header>
      <textarea
        v-model="ocrText"
        class="ocr-textarea"
        maxlength="12000"
        rows="5"
        :disabled="ocrLoading"
        placeholder="图片中未识别到文字时，可在此手动补充；留空不会被判定为安全。"
        @input="markOcrCorrected"
      ></textarea>
      <footer class="ocr-review-foot">
        <span>勾选红线知识库审核后，将以此处校对后的文字作为 RAG 输入，并把文字与命中证据写入检测报告。</span>
        <small>{{ ocrText.length }}/12000</small>
        <button type="button" :disabled="ocrLoading" @click="runImageOcr">
          {{ ocrLoading ? '识别中...' : '重新识别' }}
        </button>
      </footer>
    </section>

    <section v-if="auditPackageResult" class="audit-package-result" :class="{ invalid: auditPackageResult.tamper_suspected || !auditPackageResult.payload_integrity || !auditPackageResult.recovered_matches_original }" aria-live="polite">
      <span><ShieldCheck :size="20" /></span>
      <div><b>{{ auditPackageValid ? '审计证据包核验通过' : '审计证据包需要复核' }}</b><p>{{ auditPackageSummary }}</p></div>
      <strong>{{ auditPackageValid ? '完整' : '异常' }}</strong>
    </section>
    <dl v-if="auditPackageResult?.payload" class="audit-payload-details">
      <div><dt>报告 ID</dt><dd>{{ auditPackageResult.payload.report_id || '未关联' }}</dd></div>
      <div><dt>Deepfake</dt><dd>{{ auditResultText(auditPackageResult.payload.deepfake) }}</dd></div>
      <div><dt>AI 来源</dt><dd>{{ auditResultText(auditPackageResult.payload.provenance) }}</dd></div>
      <div><dt>内容安全</dt><dd>{{ auditResultText(auditPackageResult.payload.content_safety) }}</dd></div>
      <div><dt>知识库审核</dt><dd>{{ auditResultText(auditPackageResult.payload.rag) }}</dd></div>
      <div><dt>人工复核</dt><dd>{{ auditPackageResult.payload.human_review?.status === 'pending' ? '待复核' : auditPackageResult.payload.human_review?.verdict || '未记录' }}</dd></div>
      <div v-if="auditPackageResult.payload.custom_note" class="audit-note-detail"><dt>自定义备注</dt><dd>{{ auditPackageResult.payload.custom_note }}</dd></div>
    </dl>

    <!-- RAG 文本输入 -->
    <div class="card" style="padding:12px 16px">
      <div style="font-size:12px;color:#94a3b8;margin-bottom:6px">红线知识库审核文本（RAG 检索链路，可单独审核）</div>
      <div style="display:flex;gap:8px;align-items:flex-start">
        <textarea v-model="auditText" rows="2" class="audit-textarea" placeholder="输入需要审核的文字内容..."></textarea>
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

    <section v-if="hasResults" class="result-overview" aria-live="polite">
      <div class="result-overview-heading">
        <span><CircleCheckBig :size="18" /></span>
        <div><small>REVIEW SUMMARY</small><h2>本次审核摘要</h2></div>
      </div>
      <div class="outcome-metrics">
        <div class="outcome-metric"><span>真实性结论</span><b :class="authenticityMetric.tone">{{ authenticityMetric.title }}</b><small :title="authenticityMetric.note">{{ authenticityMetric.note }}</small></div>
        <div class="outcome-metric"><span>AI 来源</span><b :class="provenanceMetricTone(sourceSummary.aiGenerated)">{{ sourceSummary.title }}</b><small>{{ sourceSummary.note }}</small></div>
        <div class="outcome-metric"><span>内容安全</span><b :class="contentMetricTone(results.content_safety?.verdict)">{{ results.content_safety ? contentVerdictLabel(results.content_safety.verdict) : '未选择' }}</b><small>{{ results.content_safety ? '按最高风险类别处置' : '本次未运行内容安全' }}</small></div>
        <div class="outcome-metric"><span>解释证据</span><b>{{ results.mllm ? '已生成' : '未选择' }}</b><small>{{ results.mllm ? '下方查看模型证据' : '本次未运行 MLLM' }}</small></div>
      </div>
    </section>

    <!-- 检测结果 -->
    <div v-if="results.face || results.deepfake || results.mllm || results.rag || results.content_safety || results.provenance" class="results-grid">
      <ProvenanceEvidencePanel v-if="results.provenance" :result="results.provenance" />
      <FaceEvidencePanel v-if="results.face" :evidence="results.face" />
      <div class="card result-card" v-if="results.deepfake"
           v-motion :initial="{opacity:0,y:20}" :enter="{opacity:1,y:0,transition:{duration:400}}">
        <div class="card-title">Deepfake 检测</div>
        <div class="result-body">
          <span class="badge" :class="results.deepfake.label === 'fake' ? 'badge-danger' : ['review', 'skipped'].includes(results.deepfake.label) ? 'badge-warn' : 'badge-success'">
            {{ results.deepfake.label === 'fake' ? '伪造' : results.deepfake.label === 'review' ? '人工复核' : results.deepfake.label === 'skipped' ? '非人脸' : '真实' }}
          </span>
          <span class="result-meta">P(fake) {{ (results.deepfake.score * 100).toFixed(1) }}% · 模型置信度 {{ (results.deepfake.confidence * 100).toFixed(1) }}%</span>
          <p class="result-note">P(fake) 是当前模型分数，不是统计准确率；置信度尚未经过独立校准。</p>
        </div>
      </div>

      <div class="card result-card" v-if="results.mllm"
           v-motion :initial="{opacity:0,y:20}" :enter="{opacity:1,y:0,transition:{duration:400,delay:100}}">
        <div class="card-title">MLLM 可解释性</div>
        <div class="result-body">
          <span class="badge" :class="verdictClass(results.mllm.verdict)">
            {{ verdictLabel(results.mllm.verdict) }}
          </span>
          <span class="result-meta">模型自报置信度 {{ (results.mllm.confidence * 100).toFixed(1) }}% · 未校准概率</span>
          <p class="result-text">{{ results.mllm.explanation }}</p>
          <div v-if="results.mllm.evidence?.length" class="tags">
            <span v-for="e in results.mllm.evidence" :key="e" class="tag">{{ e }}</span>
          </div>
        </div>
      </div>

      <div class="card result-card" v-if="results.rag"
           v-motion :initial="{opacity:0,y:20}" :enter="{opacity:1,y:0,transition:{duration:400,delay:200}}">
        <div class="card-title">红线知识库审核（RAG 检索链路）</div>
        <div class="result-body">
          <span class="badge" :class="results.rag.safe ? 'badge-success' : 'badge-danger'">
            {{ results.rag.safe ? '安全' : '风险' }}
          </span>
          <span class="result-meta">风险等级: {{ results.rag.risk_level?.toUpperCase() }}</span>
          <span class="result-meta">关键词命中 {{ results.rag.matches?.length || 0 }} 条 · 语义命中 {{ results.rag.semantic_matches?.length || 0 }} 条</span>
          <p class="result-note">RAG 输出规则风险和证据，不输出概率；ChromaDB 仅负责知识库向量检索。</p>
          <div v-if="results.rag.matched_keywords?.length" class="tags">
            <span v-for="k in results.rag.matched_keywords" :key="k" class="tag tag-danger">{{ k }}</span>
          </div>
        </div>
      </div>

      <div class="card result-card" v-if="results.content_safety"
           v-motion :initial="{opacity:0,y:20}" :enter="{opacity:1,y:0,transition:{duration:400,delay:250}}">
        <div class="card-title">图片内容安全</div>
        <div class="result-body">
          <span class="badge" :class="contentVerdictClass(results.content_safety.verdict)">
            {{ contentVerdictLabel(results.content_safety.verdict) }}
          </span>
          <span class="result-meta">综合风险 {{ Math.round(results.content_safety.risk_score * 100) }}% · {{ results.content_safety.policy_version }}</span>
          <p class="result-note">综合风险取模型 risk_score 与命中类别 confidence 的最大值；类别 confidence 不是统计校准概率。</p>
          <p class="result-text">{{ results.content_safety.summary }}</p>
          <NudeNetEvidence
            v-if="results.content_safety.specialist_evidence?.nudenet"
            :evidence="results.content_safety.specialist_evidence.nudenet"
          />
          <UnsafeBenchEvidence
            v-if="results.content_safety.specialist_evidence?.unsafe_bench"
            :evidence="results.content_safety.specialist_evidence.unsafe_bench"
          />
          <UnsafeBenchEvidence
            v-if="results.content_safety.specialist_evidence?.perspective_vision"
            :evidence="results.content_safety.specialist_evidence.perspective_vision"
            variant="perspective"
          />
          <div v-if="results.content_safety.categories?.length" class="safety-findings">
            <div v-for="item in results.content_safety.categories" :key="item.code" class="safety-finding">
              <span>{{ item.label }}</span><b>{{ Math.round(item.confidence * 100) }}%</b>
              <p>{{ item.evidence || '模型未提供可见证据，需人工复核' }}</p>
            </div>
          </div>
          <div v-else class="safe-note">未发现已定义的图片内容风险类别</div>
        </div>
      </div>
    </div>

    <details v-if="hasResults" class="score-guide">
      <summary><span>如何理解本次评分</span><small>不同模块的数值不可直接相加或横向比较</small></summary>
      <div class="score-guide-grid">
        <article><b>Deepfake 伪造概率</b><p>分类模型输出 P(fake)，当前以 0.50 为疑似伪造阈值。该分数不是统计准确率。</p></article>
        <article><b>MLLM 结论置信</b><p>多模态模型给出的自报 confidence 尚未校准，必须结合可见证据和人工复核。</p></article>
        <article><b>图片内容风险</b><p>各类别独立判断；≥80% 阻断，35%–79% 转人工复核，低于 35% 为安全。</p></article>
        <article><b>知识库审核</b><p>RAG 输出规则、来源和处置建议，不输出伪造概率；ChromaDB 只负责向量检索。</p></article>
      </div>
    </details>

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
import { ref, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { CircleCheckBig, Play, ScanSearch, ShieldCheck, SlidersHorizontal, Upload, UserCheck } from 'lucide-vue-next'
import FaceEvidencePanel from '../components/detect/FaceEvidencePanel.vue'
import NudeNetEvidence from '../components/detect/NudeNetEvidence.vue'
import UnsafeBenchEvidence from '../components/detect/UnsafeBenchEvidence.vue'
import ProvenanceEvidencePanel from '../components/detect/ProvenanceEvidencePanel.vue'
import { verifyC2paFile } from '../lib/c2paVerification'
import { getProviderAttribution } from '../lib/providerAttribution'
import { authenticitySummary, contentMetricTone, provenanceMetricTone } from '../lib/reviewSummary'
import { getWatermarkPresentation } from '../lib/watermarkPresentation'
import { buildAuditEvidencePayload } from '../lib/auditEvidencePayload'
import { useAuth } from '../composables/useAuth'

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
const auditText = ref('')
const ocrText = ref('')
const ocrStatus = ref('idle')
const ocrLoading = ref(false)
let ocrController: AbortController | null = null
let ocrRequestId = 0
const modules = ref(['deepfake', 'mllm', 'rag', 'content_safety'])
const currentStep = ref('')
const loadingElapsed = ref(0)
let auditController: AbortController | null = null
let elapsedTimer: number | null = null
const currentStepLabel = computed(() => ({
  deepfake: '正在进行 Deepfake 检测...',
  mllm: '正在进行多模态解释分析...',
  ocr: '正在识别并审核图片文字...',
  rag: '正在进行知识库审核...',
  content_safety: '正在进行图片内容安全检测...',
  parallel_analysis: '正在并行执行多模型检测...',
  report: '正在生成检测报告...',
} as Record<string, string>)[currentStep.value] || '正在初始化检测...')
const ocrStatusLabel = computed(() => ({
  idle: '等待上传',
  loading: '正在识别',
  completed: '识别完成',
  corrected: '已人工修正',
  empty: '未识别到文字',
  unavailable: 'OCR 未配置',
  failed: '识别失败',
} as Record<string, string>)[ocrStatus.value] || '状态未知')
const provenanceLoading = ref(false)
const watermarkLoading = ref(false)
const invisibleWatermarkLoading = ref(false)
const auditPackageLoading = ref(false)
const auditPackageInput = ref<HTMLInputElement | null>(null)
const auditPackageResult = ref<any>(null)
const auditEvidenceNote = ref('')
const latestReportId = ref('')
const { user } = useAuth()
let lastProvenanceRun = 0

const generateAuditWatermark = async () => {
  if (!file.value || watermarkLoading.value) return
  watermarkLoading.value = true
  try {
    const eventId = crypto.randomUUID()
    const fd = new FormData()
    fd.append('image', file.value)
    fd.append('payload', JSON.stringify(buildAuditEvidencePayload({
      eventId,
      sampleName: file.value.name,
      reportId: latestReportId.value || results.provenance?.report_id,
      customNote: auditEvidenceNote.value,
      operatorId: user.value?.username,
      results,
    })))
    const response = await fetch('/api/detect/audit-watermark/embed', { method: 'POST', body: fd })
    if (!response.ok) throw new Error((await response.json()).detail || '生成失败')
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `threshold-audit-${eventId.slice(0, 8)}.zip`
    link.click()
    URL.revokeObjectURL(url)
    ElMessage.success('2-of-3 门限审计包已生成，请分开保管三个密钥分片')
  } catch (error:any) {
    ElMessage.error(error?.message || '审计副本生成失败')
  } finally {
    watermarkLoading.value = false
  }
}

const selectAuditPackage = () => auditPackageInput.value?.click()

const verifyAuditPackage = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const archive = input.files?.[0]
  input.value = ''
  if (!archive || auditPackageLoading.value) return
  auditPackageLoading.value = true
  auditPackageResult.value = null
  try {
    const fd = new FormData()
    fd.append('archive', archive)
    const response = await fetch('/api/detect/audit-watermark/decode-archive', { method: 'POST', body: fd })
    if (!response.ok) throw new Error((await response.json()).detail || '证据包核验失败')
    auditPackageResult.value = await response.json()
    if (auditPackageValid.value) ElMessage.success('审计证据包核验通过')
    else ElMessage.warning('审计证据包存在异常，请人工复核')
  } catch (error:any) {
    ElMessage.error(error?.message || '无法读取该审计证据包')
  } finally {
    auditPackageLoading.value = false
  }
}

const auditPackageValid = computed(() => !!auditPackageResult.value
  && auditPackageResult.value.payload_integrity
  && auditPackageResult.value.recovered_matches_original
  && !auditPackageResult.value.tamper_suspected)
const auditPackageSummary = computed(() => {
  const result = auditPackageResult.value
  if (!result) return ''
  const eventId = result.payload?.event_id || '未提供'
  return `事件 ${eventId} · 载荷${result.payload_integrity ? '完整' : '异常'} · 原始像素${result.recovered_matches_original ? '恢复一致' : '不一致'}`
})
const auditResultText = (item:any) => {
  if (!item || item.status === 'not_run') return '未执行'
  if (item.label) return `${item.label}${typeof item.score === 'number' ? ` · ${(item.score * 100).toFixed(1)}%` : ''}`
  if (item.state) return `${item.state}${item.provider ? ` · ${item.provider}` : ''}`
  if (item.verdict) return `${item.verdict}${typeof item.risk_score === 'number' ? ` · ${(item.risk_score * 100).toFixed(1)}%` : ''}`
  if (typeof item.safe === 'boolean') return item.safe ? '安全' : `风险 · ${item.risk_level || '未分级'}`
  return '已执行'
}

const generateInvisibleWatermark = async () => {
  if (!file.value || invisibleWatermarkLoading.value) return
  invisibleWatermarkLoading.value = true
  try {
    const contentId = crypto.randomUUID()
    const fd = new FormData()
    fd.append('image', file.value)
    fd.append('payload', JSON.stringify({
      content_id: contentId,
      content_type: 'ai_generated',
      provider: 'aigc-safety-system',
    }))
    const response = await fetch('/api/detect/invisible-watermark/embed', { method: 'POST', body: fd })
    if (!response.ok) throw new Error((await response.json()).detail || '嵌入失败')
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `platform-watermarked-${contentId.slice(0, 8)}.png`
    link.click()
    URL.revokeObjectURL(url)
    ElMessage.success('已生成带本平台签名隐形水印的图片')
  } catch (error:any) {
    ElMessage.error(error?.message || '隐形标识生成失败')
  } finally {
    invisibleWatermarkLoading.value = false
  }
}

const hasResults = computed(() => Object.keys(results).length > 0)
const authenticityMetric = computed(() => authenticitySummary(results.deepfake, results.mllm))
const provenanceAttribution = computed(() => {
  const local = results.provenance?.local_c2pa || {}
  const valid = results.provenance?.source_evidence?.content_credentials?.status === 'valid' && local.verdict !== 'invalid'
  return getProviderAttribution(local.claimGenerator || results.provenance?.source_evidence?.content_credentials?.claim_generator || '', local.sourceType || '', valid)
})
const watermarkPresentation = computed(() => getWatermarkPresentation(results.provenance?.source_evidence?.watermark))
const sourceSummary = computed(() => {
  if (!results.provenance) return { title: '未验证', note: '本次未运行来源验证', aiGenerated: false }
  if (provenanceAttribution.value.aiGenerated) return {
    title: `${provenanceAttribution.value.provider} AI 生成`,
    note: 'C2PA 生成来源证据有效',
    aiGenerated: true,
  }
  if (watermarkPresentation.value.aiGenerated) return {
    title: '本平台 AI 标识已验证',
    note: '平台签名隐形水印有效，不代表第三方厂商来源',
    aiGenerated: true,
  }
  if (provenanceAttribution.value.provider !== '未知') return {
    title: `${provenanceAttribution.value.provider} 来源凭证`,
    note: '已识别签发工具，AI 生成未确认',
    aiGenerated: false,
  }
  return { title: '未确认 AI 生成来源', note: '未发现可确认的来源信号', aiGenerated: false }
})

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
const contentVerdictClass = (v: string) =>
  v === 'unsafe' ? 'badge-danger' : v === 'safe' ? 'badge-success' : 'badge-warn'
const contentVerdictLabel = (v: string) =>
  v === 'unsafe' ? '阻断' : v === 'safe' ? '安全' : '人工复核'

const onFileChange = (f: any) => {
  if (preview.value) URL.revokeObjectURL(preview.value)
  file.value = f.raw
  preview.value = URL.createObjectURL(f.raw)
  delete results.provenance
  ocrText.value = ''
  ocrStatus.value = 'idle'
  void runImageOcr()
}

const runImageOcr = async () => {
  if (!file.value) return
  ocrController?.abort()
  const requestId = ++ocrRequestId
  const controller = new AbortController()
  ocrController = controller
  ocrLoading.value = true
  ocrStatus.value = 'loading'
  const timeout = window.setTimeout(() => controller.abort(), 90_000)
  try {
    const form = new FormData()
    form.append('image', file.value)
    const response = await fetch('/api/detect/ocr', {
      method: 'POST', body: form, signal: controller.signal,
    })
    if (!response.ok) throw new Error(`OCR 服务响应异常（HTTP ${response.status}）`)
    const payload = await response.json()
    if (requestId !== ocrRequestId) return
    ocrText.value = String(payload.text || '').slice(0, 12_000)
    ocrStatus.value = payload.status || (ocrText.value ? 'completed' : 'empty')
    if (ocrStatus.value === 'unavailable') ElMessage.warning('OCR 服务未配置，可手动填写图片文字后继续审核')
    else if (ocrStatus.value === 'failed') ElMessage.warning('图片文字识别失败，可重新识别或手动填写')
  } catch (error:any) {
    if (requestId !== ocrRequestId) return
    ocrStatus.value = 'failed'
    if (error?.name !== 'AbortError') ElMessage.error(error?.message || '图片文字识别失败')
    else ElMessage.warning('图片文字识别超时，可重新识别或手动填写')
  } finally {
    window.clearTimeout(timeout)
    if (requestId === ocrRequestId) {
      ocrLoading.value = false
      ocrController = null
    }
  }
}

const markOcrCorrected = () => {
  if (!ocrLoading.value) ocrStatus.value = 'corrected'
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

const runProvenance = async () => {
  if (!file.value || provenanceLoading.value) return
  const now = Date.now()
  if (now - lastProvenanceRun < 800) return
  lastProvenanceRun = now
  provenanceLoading.value = true
  try {
    const fd = new FormData(); fd.append('image', file.value); fd.append('save_report', 'true')
    const [response, localResult] = await Promise.all([
      fetch('/api/detect/provenance', { method:'POST', body:fd }),
      verifyC2paFile(file.value).catch((error) => ({ error: error instanceof Error ? error.message : 'local_verify_failed' })),
    ])
    if (!response.ok) throw new Error('verify_failed')
    results.provenance = { ...await response.json(), local_c2pa: localResult }
    const attribution = provenanceAttribution.value
    if (attribution.aiGenerated) {
      ElMessage.success(`${attribution.provider} AI 生成内容：C2PA 来源凭证验证通过`)
    } else if (results.provenance.overall_state === 'confirmed_source') {
      ElMessage.success('来源凭证已验证：Content Credentials 与当前文件绑定通过')
    } else if (results.provenance.overall_state === 'invalid_or_tampered') {
      ElMessage.warning('来源声明验证失败或文件可能已被修改，请人工复核')
    } else {
      ElMessage.info('来源验证完成，请查看证据说明')
    }
    if (results.provenance.report_id) {
      ElMessage.success(`来源验证报告已保存：${results.provenance.report_id.slice(0, 8)}`)
    }
  } catch { ElMessage.error('来源验证失败，请检查图片格式') }
  finally { provenanceLoading.value = false }
}

const runAudit = async () => {
  if (!file.value && !auditText.value.trim()) { ElMessage.warning('请上传图像或输入文本'); return }
  loading.value = true
  currentStep.value = 'initializing'
  loadingElapsed.value = 0
  Object.keys(results).forEach(k => delete results[k])

  const form = new FormData()
  if (file.value) form.append('image', file.value)
  if (auditText.value.trim()) form.append('text', auditText.value.trim())
  if (file.value && modules.value.includes('rag')) {
    form.append('ocr_text', ocrText.value.trim())
    form.append('ocr_status', ocrStatus.value)
  }
  form.append('modules', modules.value.join(','))

  auditController?.abort()
  auditController = new AbortController()
  let timedOut = false
  const hardTimeout = window.setTimeout(() => {
    timedOut = true
    auditController?.abort()
  }, 300_000)
  elapsedTimer = window.setInterval(() => loadingElapsed.value++, 1000)
  let completed = false

  try {
    const resp = await fetch('/api/detect/full', {
      method: 'POST', body: form, signal: auditController.signal,
    })
    if (!resp.ok || !resp.body) throw new Error(`检测服务响应异常（HTTP ${resp.status}）`)
    const reader = resp.body.getReader()
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
        if (event === 'face') results.face = payload
        if (event === 'deepfake') results.deepfake = payload
        if (event === 'mllm') results.mllm = payload
        if (event === 'ocr') {
          if (ocrStatus.value !== 'corrected') ocrText.value = String(payload.text || '').slice(0, 12_000)
          if (ocrStatus.value !== 'corrected') ocrStatus.value = payload.status || 'completed'
        }
        if (event === 'rag') results.rag = payload
        if (event === 'content_safety') results.content_safety = payload
        if (event === 'provenance') results.provenance = payload
        if (event === 'done') {
          completed = true
          if (payload.report_id) {
            latestReportId.value = payload.report_id
            const ids = new Set<string>(JSON.parse(localStorage.getItem('report_ids') || '[]'))
            ids.add(payload.report_id)
            localStorage.setItem('report_ids', JSON.stringify([...ids]))
          }
        }
      }
    }
    if (!completed) throw new Error('检测连接提前结束，请重试')
  } catch (error:any) {
    if (error?.name === 'AbortError') {
      ElMessage.warning(timedOut ? '检测超过 5 分钟，已自动停止' : '已取消本次检测')
    } else {
      ElMessage.error(error?.message || '检测连接异常，请重试')
    }
  } finally {
    window.clearTimeout(hardTimeout)
    if (elapsedTimer !== null) window.clearInterval(elapsedTimer)
    elapsedTimer = null
    auditController = null
    loading.value = false
    currentStep.value = ''
  }
}

const cancelAudit = () => auditController?.abort()
const moduleIsRunning = (name: string) => loading.value
  && modules.value.includes(name)
  && ['parallel_analysis', name].includes(currentStep.value)
</script>

<style scoped>
.detect-page{max-width:1180px;margin:0 auto;display:flex;flex-direction:column;gap:16px}.top-grid{display:grid;grid-template-columns:260px 1fr 280px;gap:14px}.info-card{display:flex;align-items:center;gap:14px}.avatar-wrap{position:relative;flex-shrink:0}.avatar-img,.avatar-placeholder{width:56px;height:56px;border-radius:6px;object-fit:cover}.avatar-placeholder{display:grid;place-items:center;background:#0b1218}.avatar-dot{position:absolute;right:-3px;bottom:-3px;width:11px;height:11px;border:2px solid var(--surface);border-radius:50%}.dot-ready{background:var(--success)}.dot-idle{background:var(--faint)}.info-name{max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text);font-size:14px;font-weight:600}.info-sub,.result-meta,.ring-label{color:var(--muted);font-size:11px}.sys-rows{display:flex;flex-direction:column;gap:10px}.sys-row{display:flex;align-items:center;gap:8px;font-size:12px}.sys-dot{width:6px;height:6px;border-radius:50%;background:var(--primary)}.sys-label{flex:1;color:var(--muted)}.sys-val{color:var(--text);font:11px ui-monospace,monospace}.ring-card{display:flex;align-items:center;justify-content:center}.ring-wrap{display:flex;gap:24px}.ring-item{position:relative;display:flex;flex-direction:column;align-items:center;gap:6px}.ring-svg{width:82px;height:82px;transform:rotate(-90deg)}.ring-bg{fill:none;stroke:var(--line);stroke-width:7}.ring-fill{fill:none;stroke-width:7;stroke-linecap:round;stroke-dasharray:239;transition:stroke-dashoffset .7s}.ring-pink{stroke:var(--primary)}.ring-purple{stroke:var(--warning)}.ring-center{position:absolute;top:40px;left:50%;display:flex;align-items:baseline;transform:translate(-50%,-50%)}.ring-val{color:var(--primary);font-size:20px;font-weight:700}.ring-val-purple{color:var(--warning)}.ring-unit{color:var(--primary);font-size:10px}.stats-row{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}.stat-box{padding:12px;text-align:center;background:#0d161d;border:1px solid var(--line);border-radius:6px}.stat-main{border-color:rgba(45,212,191,.32);background:rgba(45,212,191,.06)}.stat-num{color:var(--text);font-size:18px;font-weight:700}.stat-label{margin-top:3px;color:var(--muted);font-size:10px}.num-done{color:var(--success)}.num-idle{color:var(--faint)}.num-running{color:var(--warning)}.action-row{display:flex;gap:14px}.upload-zone{flex:1}.upload-zone :deep(.el-upload-dragger){padding:22px!important;border-radius:7px!important}.upload-inner{display:flex;flex-direction:column;align-items:center;gap:6px}.upload-text{color:var(--text);font-size:13px}.upload-sub{color:var(--faint);font-size:11px}.detect-btn,.send-btn{min-height:39px;padding:0 18px;color:#06110f;background:var(--primary);border:0;border-radius:6px;font-size:12px;font-weight:700;cursor:pointer}.detect-btn{width:190px}.detect-btn:disabled,.send-btn:disabled{opacity:.45}.results-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.result-body{display:flex;flex-direction:column;gap:9px}.badge{display:inline-flex;width:max-content;padding:3px 9px;font-size:11px;font-weight:600}.result-text{margin:0;color:var(--muted);font-size:12px;line-height:1.65}.tags{display:flex;flex-wrap:wrap;gap:5px}.tag{padding:3px 7px;color:var(--primary);background:rgba(45,212,191,.07);border:1px solid rgba(45,212,191,.18);border-radius:4px;font-size:10px}.tag-danger{color:var(--danger);background:rgba(251,113,133,.08);border-color:rgba(251,113,133,.22)}.scan-overlay{position:fixed;inset:0;z-index:100;display:grid;place-items:center;background:rgba(3,8,11,.78);backdrop-filter:blur(4px)}.scan-box{position:relative;width:270px;height:270px;overflow:hidden;background:#0b1218;border:1px solid var(--primary);border-radius:7px;box-shadow:0 0 40px rgba(45,212,191,.15)}.scan-line{position:absolute;left:0;width:100%;height:2px;background:linear-gradient(90deg,transparent,var(--primary),transparent);box-shadow:0 0 12px var(--primary);animation:scan 2s linear infinite}.scan-text{position:absolute;bottom:20px;width:100%;text-align:center;color:var(--primary);font-size:12px}.quote-card{position:relative;padding:18px;text-align:center}.quote-icon{display:none}.quote-text{margin-bottom:8px;color:var(--muted);font-size:13px}.quote-source{color:var(--primary);font-size:11px}.quote-author{color:var(--faint);font-size:10px}.quote-refresh{position:absolute;top:12px;right:12px;color:var(--faint);background:transparent;border:0;cursor:pointer}@keyframes scan{from{top:0}to{top:100%}}@media(max-width:900px){.top-grid{grid-template-columns:1fr 1fr}.ring-card{grid-column:1/-1}.stats-row{grid-template-columns:repeat(3,1fr)}}@media(max-width:650px){.top-grid,.results-grid{grid-template-columns:1fr}.ring-card{grid-column:auto}.action-row{flex-direction:column}.stats-row{grid-template-columns:repeat(2,1fr)}.detect-btn{width:100%}}
.audit-textarea{flex:1;min-width:0;padding:10px 12px;color:var(--text);background:#0b1218;border:1px solid var(--line-bright);border-radius:6px;font-size:13px;line-height:1.55;resize:vertical;outline:none}.audit-textarea::placeholder{color:var(--faint)}.audit-textarea:focus{border-color:var(--primary);box-shadow:0 0 0 2px rgba(45,212,191,.1)}
.avatar-placeholder,.stat-box{background:var(--surface-2)}
.stat-main{border-color:rgba(8,126,174,.28);background:rgba(8,126,174,.055)}
.detect-btn,.send-btn{color:#fff}
.tag{background:rgba(8,126,174,.07);border-color:rgba(8,126,174,.2)}
.tag-danger{background:rgba(207,63,79,.08);border-color:rgba(207,63,79,.22)}
.audit-textarea{background:#fff;box-shadow:inset 0 1px 2px rgba(23,40,56,.03)}
.audit-textarea:focus{box-shadow:0 0 0 3px rgba(8,126,174,.1)}
.scan-overlay{background:rgba(16,40,60,.48)}
.scan-box{background:#fff;box-shadow:0 20px 56px rgba(16,40,60,.2)}
.source-btn{min-height:34px;padding:0 14px;color:var(--primary);background:#fff;border:1px solid var(--primary);border-radius:6px;font-size:12px;font-weight:700;cursor:pointer}.source-btn:disabled{opacity:.45;cursor:not-allowed}
.sys-rows{gap:8px}.stats-row{grid-template-columns:repeat(auto-fit,minmax(140px,1fr))}.safety-findings{display:flex;flex-direction:column;gap:7px}.safety-finding{display:grid;grid-template-columns:1fr auto;gap:4px 10px;padding:9px 10px;background:#f7fafc;border-left:3px solid var(--danger)}.safety-finding span{color:var(--text);font-size:11px;font-weight:650}.safety-finding b{color:var(--danger);font:11px ui-monospace,monospace}.safety-finding p{grid-column:1/3;margin:0;color:var(--muted);font-size:10px;line-height:1.5}.safe-note{padding:9px 10px;color:var(--success);background:rgba(22,128,94,.06);border:1px solid rgba(22,128,94,.16);border-radius:5px;font-size:10px}
.detect-page{max-width:1280px;gap:14px}
.top-grid{grid-template-columns:minmax(220px,.75fr) minmax(340px,1.35fr) minmax(250px,.9fr);gap:12px}
.top-grid>.card{min-height:174px;padding:18px}
.info-card{position:relative;padding-top:48px!important}
.card-eyebrow{position:absolute;top:16px;left:18px;color:var(--primary);font-size:11px;font-weight:700;letter-spacing:.04em}
.info-name{max-width:190px;font-size:15px}.info-sub{margin-top:5px}
.sys-card .card-title,.ring-card .card-title{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin-bottom:13px}
.sys-card .card-title,.ring-card .card-title{text-align:left}
.sys-card .card-title small,.ring-card .card-title small{color:var(--faint);font-size:9px;font-weight:400}
.ring-card{flex-direction:column;align-items:stretch!important;justify-content:flex-start!important}.ring-card .ring-wrap{margin:auto}.ring-wrap{gap:34px}.ring-svg{width:88px;height:88px}.ring-center{top:43px}
.stats-row{grid-template-columns:repeat(6,minmax(0,1fr));gap:8px}.stat-box{min-height:68px;padding:11px 9px}.stat-num{font-size:17px}.stat-label{font-size:10px}
.action-row{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:12px;align-items:stretch}.upload-zone,.upload-zone :deep(.el-upload){display:flex;min-width:0}.upload-zone :deep(.el-upload){width:100%;flex:1}.upload-zone :deep(.el-upload-dragger){min-height:252px;height:auto;display:grid;place-items:center;flex:1;padding:18px!important}.upload-inner{gap:8px}.upload-text{font-size:14px}
.ocr-review{display:flex;flex-direction:column;gap:10px;padding:14px 16px;background:var(--surface);border:1px solid var(--line);border-radius:8px;box-shadow:var(--shadow-sm)}.ocr-review-head,.ocr-review-foot{display:flex;align-items:center;gap:12px}.ocr-review-head>span{display:flex;min-width:0;flex:1;flex-direction:column;gap:2px}.ocr-review-head small{color:var(--primary);font-size:8px;font-weight:750}.ocr-review-head b{color:var(--text);font-size:13px}.ocr-status{padding:4px 8px;border:1px solid var(--line);border-radius:4px;color:var(--muted);background:var(--surface-2);font-size:10px;font-style:normal;font-weight:700}.ocr-status-completed,.ocr-status-corrected{color:var(--success);border-color:rgba(22,128,94,.25);background:rgba(22,128,94,.06)}.ocr-status-loading{color:var(--primary);border-color:rgba(8,126,174,.25);background:rgba(8,126,174,.06)}.ocr-status-empty,.ocr-status-unavailable,.ocr-status-failed{color:var(--warning);border-color:rgba(194,126,0,.28);background:rgba(194,126,0,.07)}.ocr-textarea{box-sizing:border-box;width:100%;min-height:108px;padding:10px 12px;resize:vertical;color:var(--text);background:#fff;border:1px solid var(--line);border-radius:6px;font:12px/1.65 var(--font-body, sans-serif);outline:none}.ocr-textarea:focus{border-color:var(--primary);box-shadow:0 0 0 3px rgba(8,126,174,.1)}.ocr-textarea:disabled{opacity:.68}.ocr-review-foot>span{min-width:0;flex:1;color:var(--muted);font-size:10px;line-height:1.5}.ocr-review-foot>small{color:var(--faint);font-size:9px;white-space:nowrap}.ocr-review-foot>button{min-height:30px;padding:0 12px;color:var(--primary);background:var(--surface-2);border:1px solid var(--line-bright);border-radius:5px;font-size:10px;font-weight:700;cursor:pointer}.ocr-review-foot>button:disabled{cursor:not-allowed;opacity:.5}
.control-panel{display:flex;flex-direction:column;gap:9px;padding:16px;background:var(--surface);border:1px solid var(--line);border-radius:8px;box-shadow:var(--shadow-sm)}
.module-heading{display:flex;align-items:baseline;justify-content:space-between;color:var(--text);font-size:13px;font-weight:700}.module-heading small{color:var(--faint);font-size:10px;font-weight:400}.module-group{display:flex;flex-direction:column;gap:5px;padding-top:8px;border-top:1px solid var(--line)}.module-group>b{margin-bottom:2px;color:var(--muted);font-size:10px;font-weight:700}.module-option{display:grid;grid-template-columns:16px 1fr auto;align-items:center;gap:6px;min-height:27px;color:var(--text);font-size:11px;cursor:pointer}.module-option input{width:14px;height:14px;accent-color:var(--primary)}.module-option small{color:var(--faint);font-size:9px}.module-actions{display:flex;flex-direction:column;gap:7px;margin-top:auto;padding-top:5px}.module-actions .source-btn,.module-actions .detect-btn{width:100%;min-height:36px}.module-actions .source-btn{font-size:11px}.module-actions .detect-btn{font-size:12px}
.visually-hidden{position:absolute!important;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}.audit-package-result{display:flex;align-items:center;gap:10px;margin:10px 0;padding:12px 14px;border:1px solid #b9dcd5;border-radius:7px;background:#f3fbf9;color:#087c67}.audit-package-result>div{min-width:0;flex:1}.audit-package-result b{font-size:13px}.audit-package-result p{margin:3px 0 0;color:var(--muted);font-size:11px}.audit-package-result strong{font-size:11px}.audit-package-result.invalid{border-color:#edc4cb;background:#fff7f8;color:#bd3042}
.audit-note-field{display:flex;flex-direction:column;gap:4px;padding-top:8px;border-top:1px solid var(--line)}.audit-note-field span{color:var(--muted);font-size:10px;font-weight:700}.audit-note-field textarea{box-sizing:border-box;width:100%;resize:vertical;padding:7px 8px;border:1px solid var(--line);border-radius:5px;color:var(--text);background:#fff;font:inherit;font-size:10px;line-height:1.4}.audit-note-field small{color:var(--faint);font-size:9px}.audit-payload-details{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;margin:0 0 12px;overflow:hidden;border:1px solid var(--line);border-radius:7px;background:var(--line)}.audit-payload-details div{min-width:0;padding:10px 12px;background:#fff}.audit-payload-details dt{color:var(--faint);font-size:10px}.audit-payload-details dd{overflow:hidden;margin:4px 0 0;color:var(--text);font-size:11px;font-weight:600;text-overflow:ellipsis;white-space:nowrap}.audit-payload-details .audit-note-detail{grid-column:1/-1}.audit-payload-details .audit-note-detail dd{white-space:normal;line-height:1.5}@media(max-width:800px){.audit-payload-details{grid-template-columns:1fr 1fr}}
.card[style*="padding:12px 16px"]{padding:16px!important}.card[style*="padding:12px 16px"]>div:first-child{margin-bottom:9px!important;color:var(--text)!important;font-size:12px!important;font-weight:700}.audit-textarea{min-height:76px}
.results-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.result-card{min-height:146px}.result-card .card-title{display:flex;align-items:center;gap:8px}.result-card .card-title::before{content:'';width:3px;height:15px;background:var(--primary);border-radius:2px}.result-body{gap:10px}
@media(max-width:1050px){.top-grid{grid-template-columns:1fr 1fr}.ring-card{grid-column:1/-1}.stats-row{grid-template-columns:repeat(3,minmax(0,1fr))}.action-row{grid-template-columns:minmax(0,1fr) 280px}}
@media(max-width:700px){.top-grid,.results-grid{grid-template-columns:1fr}.ring-card{grid-column:auto}.action-row{grid-template-columns:1fr}.upload-zone :deep(.el-upload-dragger){height:220px}.control-panel{padding:13px}.module-option{font-size:12px}.module-option small{font-size:10px}}
@media(max-width:700px){.ocr-review-head,.ocr-review-foot{align-items:flex-start;flex-wrap:wrap}.ocr-review-foot>span{flex-basis:100%}.ocr-review-foot>button{margin-left:auto}}
.outcome-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin:auto 0}.outcome-metric{display:flex;min-width:0;flex-direction:column;gap:5px;padding:10px 8px;background:var(--surface-2);border:1px solid var(--line);border-radius:5px}.outcome-metric span,.outcome-metric small{overflow:hidden;color:var(--muted);font-size:9px;text-overflow:ellipsis;white-space:nowrap}.outcome-metric b{overflow:hidden;color:var(--text);font-size:14px;text-overflow:ellipsis;white-space:nowrap}.outcome-metric b.badge-success{color:var(--success)}.outcome-metric b.badge-danger,.outcome-metric b.metric-danger{color:var(--danger)}.outcome-metric b.badge-warn{color:var(--warning)}
.score-guide{background:var(--surface);border:1px solid var(--line);border-radius:7px;box-shadow:var(--shadow-sm)}.score-guide summary{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 14px;color:var(--text);cursor:pointer;font-size:12px;font-weight:700;list-style:none}.score-guide summary::-webkit-details-marker{display:none}.score-guide summary::after{order:-1;content:'+';display:grid;width:18px;height:18px;place-items:center;color:var(--primary);background:var(--surface-2);border:1px solid var(--line);border-radius:4px;font-size:15px;font-weight:400}.score-guide[open] summary::after{content:'−'}.score-guide summary span{margin-right:auto}.score-guide summary small{color:var(--faint);font-size:10px;font-weight:400}.score-guide-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;padding:0 14px 14px}.score-guide-grid article{padding:10px;background:var(--surface-2);border-left:3px solid var(--primary)}.score-guide-grid b{color:var(--text);font-size:11px}.score-guide-grid p{margin:6px 0 0;color:var(--muted);font-size:10px;line-height:1.6}
.calibration-status{padding:16px;background:var(--surface);border:1px solid var(--line);border-radius:7px;box-shadow:var(--shadow-sm)}.calibration-head{display:flex;align-items:center;justify-content:space-between;gap:12px}.calibration-head h2{margin:3px 0 0;color:var(--text);font-size:14px}.calibration-badge{padding:4px 9px;border-radius:4px;font-size:10px;font-weight:700}.calibration-smoke_only{color:#9a6500;background:#fff7df;border:1px solid #ecd58c}.calibration-not_calibrated{color:var(--muted);background:var(--surface-2);border:1px solid var(--line)}.calibration-calibrated{color:#167e5e;background:#e8f7f0;border:1px solid #a9dfc9}.calibration-claim{margin:10px 0;color:var(--muted);font-size:11px;line-height:1.55}.calibration-tasks{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:7px}.calibration-task{display:grid;grid-template-columns:1fr auto;gap:4px 8px;padding:9px 10px;background:var(--surface-2);border:1px solid var(--line);border-radius:5px}.calibration-task span{overflow:hidden;color:var(--text);font-size:11px;text-overflow:ellipsis;white-space:nowrap}.calibration-task b{color:var(--warning);font-size:10px}.calibration-task small{grid-column:1/-1;color:var(--faint);font-size:9px}.calibration-task .task-protocol{overflow:hidden;color:var(--muted);text-overflow:ellipsis;white-space:nowrap}.calibration-boundary{display:block;margin-top:9px;color:var(--faint);font-size:10px;line-height:1.5}
@media(max-width:1050px){.outcome-metrics{max-width:600px}.score-guide-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:700px){.outcome-metrics,.score-guide-grid{grid-template-columns:1fr}.score-guide summary{align-items:flex-start;flex-wrap:wrap}.score-guide summary small{width:100%;padding-left:30px}}
.calibration-status .card-eyebrow{position:static;display:block}.calibration-partially_calibrated{color:#8a5b00;background:#fff7df;border:1px solid #ecd58c}.calibration-tasks{grid-template-columns:repeat(3,minmax(0,1fr))}.calibration-task span{overflow:visible;font-size:12px;text-overflow:clip;white-space:normal}.calibration-task small{font-size:10px}@media(max-width:900px){.calibration-tasks{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){.calibration-tasks{grid-template-columns:1fr}}
.calibration-task .task-evidence{overflow:hidden;color:var(--faint);text-overflow:ellipsis;white-space:nowrap}
.calibration-task .task-ci{color:var(--muted);line-height:1.45}
.result-note{margin:0;color:var(--faint);font-size:10px;line-height:1.55}
.task-header{display:flex;align-items:center;justify-content:space-between;gap:28px;padding:6px 2px 14px;border-bottom:1px solid var(--line)}.task-heading{display:flex;align-items:center;gap:13px;min-width:280px}.task-heading-icon{width:44px;height:44px;display:grid;place-items:center;flex:0 0 44px;color:#fff;background:var(--primary);border-radius:7px;box-shadow:0 8px 18px rgba(8,126,174,.17)}.task-kicker{color:var(--primary);font-size:9px;font-weight:750}.task-heading h1{margin:3px 0 2px;font-size:20px;line-height:1.2}.task-heading p{margin:0;color:var(--muted);font-size:10px;line-height:1.5}.workflow-steps{display:grid;grid-template-columns:repeat(4,minmax(118px,1fr));min-width:min(660px,62%);border:1px solid var(--line);border-radius:7px;overflow:hidden;background:var(--surface)}.workflow-step{position:relative;display:flex;align-items:center;gap:8px;min-width:0;padding:11px 12px;color:var(--faint);border-right:1px solid var(--line)}.workflow-step:last-child{border-right:0}.workflow-step::after{content:'';position:absolute;left:0;right:100%;bottom:0;height:2px;background:var(--primary);transition:right .25s ease}.workflow-step.active{color:var(--primary);background:rgba(8,126,174,.035)}.workflow-step.active::after,.workflow-step.done::after{right:0}.workflow-step.done{color:var(--success)}.workflow-step>svg{flex:0 0 auto}.workflow-step span{min-width:0}.workflow-step b,.workflow-step small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.workflow-step b{color:var(--text);font-size:10px}.workflow-step small{margin-top:2px;color:inherit;font-size:8px}.stats-row{grid-template-columns:repeat(4,minmax(0,1fr))}.upload-preview{width:min(240px,82%);height:152px;object-fit:contain;background:var(--surface-2);border:1px solid var(--line);border-radius:6px}.result-overview{display:grid;grid-template-columns:220px 1fr;align-items:stretch;background:var(--surface);border:1px solid var(--line);border-radius:8px;overflow:hidden;box-shadow:var(--shadow-sm)}.result-overview-heading{display:flex;align-items:center;gap:10px;padding:16px 18px;background:var(--surface-2);border-right:1px solid var(--line)}.result-overview-heading>span{width:34px;height:34px;display:grid;place-items:center;color:var(--success);background:rgba(22,128,94,.08);border-radius:5px}.result-overview-heading small{color:var(--primary);font-size:8px;font-weight:750}.result-overview-heading h2{margin:3px 0 0;font-size:14px}.result-overview .outcome-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0;margin:0}.result-overview .outcome-metric{justify-content:center;padding:13px 16px;background:#fff;border:0;border-right:1px solid var(--line);border-radius:0}.result-overview .outcome-metric:last-child{border-right:0}.result-overview .outcome-metric span,.result-overview .outcome-metric small{font-size:9px}.result-overview .outcome-metric b{font-size:15px}
@media(max-width:1050px){.task-header{align-items:flex-start;flex-direction:column}.workflow-steps{width:100%;min-width:0}.result-overview{grid-template-columns:180px 1fr}}
@media(max-width:700px){.task-heading{min-width:0}.task-heading h1{font-size:18px}.workflow-steps{grid-template-columns:1fr 1fr}.workflow-step:nth-child(2){border-right:0}.workflow-step:nth-child(-n+2){border-bottom:1px solid var(--line)}.stats-row{grid-template-columns:repeat(2,minmax(0,1fr))}.result-overview{grid-template-columns:1fr}.result-overview-heading{border-right:0;border-bottom:1px solid var(--line)}.result-overview .outcome-metrics{grid-template-columns:1fr}.result-overview .outcome-metric{border-right:0;border-bottom:1px solid var(--line)}.result-overview .outcome-metric:last-child{border-bottom:0}}
.result-overview .outcome-metrics{grid-template-columns:repeat(4,minmax(0,1fr))}
.result-overview .outcome-metric b.metric-success{color:var(--success);background:transparent}.result-overview .outcome-metric b.metric-warn{color:var(--warning);background:transparent}.result-overview .outcome-metric b.metric-danger{color:var(--danger);background:transparent}
.result-overview .outcome-metric small{display:-webkit-box;overflow:hidden;line-height:1.35;white-space:normal;-webkit-box-orient:vertical;-webkit-line-clamp:2}
.scan-text{bottom:58px}.scan-meta{position:absolute;bottom:38px;width:100%;text-align:center;color:var(--faint);font-size:9px}.scan-cancel{position:absolute;bottom:10px;left:50%;min-height:24px;padding:0 11px;transform:translateX(-50%);color:var(--muted);background:var(--surface-2);border:1px solid var(--line);border-radius:4px;font-size:9px;cursor:pointer}.scan-cancel:hover{color:var(--danger);border-color:var(--danger)}
@media(max-width:700px){.result-overview .outcome-metrics{grid-template-columns:1fr}}
</style>
