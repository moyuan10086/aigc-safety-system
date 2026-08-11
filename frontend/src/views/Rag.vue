<template>
  <div class="rag-page">
    <header class="page-head">
      <div>
        <p class="eyebrow">REDLINE RETRIEVAL</p>
        <h1>红线检索策略</h1>
        <p>面向安全审核的混合检索、证据重排与引用溯源工作台</p>
      </div>
      <span class="health"><i></i>{{ loading ? '读取中' : '引擎可用' }}</span>
    </header>

    <section class="metrics">
      <article><span>知识文件</span><b>{{ stats.file_count ?? 0 }}</b><small>已入库数据源</small></article>
      <article><span>有效分块</span><b>{{ stats.chunk_count ?? 0 }}</b><small>可检索证据单元</small></article>
      <article><span>RAG 检索链路</span><b class="metric-text">混合召回</b><small>向量 70% + 词法 30%</small></article>
      <article><span>默认阈值</span><b>{{ stats.score_threshold ?? 0.32 }}</b><small>低于阈值不进入上下文</small></article>
    </section>

    <section class="pipeline-panel panel">
      <div class="panel-title"><div><b>检索链路</b><span>参考 FastGPT / RAGFlow 的可观察检索流程</span></div><span class="version">RAG v2</span></div>
      <div class="pipeline">
        <div class="stage"><strong>01</strong><b>文档解析</b><span>PDF / DOCX / TXT / OCR</span></div>
        <div class="connector">→</div>
        <div class="stage"><strong>02</strong><b>结构化切分</b><span>段落感知 · 500 / 50</span></div>
        <div class="connector">→</div>
        <div class="stage"><strong>03</strong><b>双路召回</b><span>语义向量 + 中文词法</span></div>
        <div class="connector">→</div>
        <div class="stage"><strong>04</strong><b>融合重排</b><span>分项分数 · 阈值过滤</span></div>
        <div class="connector">→</div>
        <div class="stage"><strong>05</strong><b>证据输出</b><span>来源、分块与引用编号</span></div>
      </div>
    </section>

    <div class="workspace-grid">
      <section class="panel search-panel">
        <div class="panel-title"><div><b>单点检索测试</b><span>先验证召回证据，再接入生成回答</span></div></div>
        <label class="query-label" for="rag-query">测试问题</label>
        <textarea id="rag-query" v-model="query" rows="4" maxlength="4000" placeholder="例如：发现个人信息泄露后应如何处置？" />
        <div class="controls">
          <label>分类过滤<select v-model="category"><option value="">全部分类</option><option v-for="item in stats.categories || []" :key="item">{{ item }}</option></select></label>
          <label>Top-K<input v-model.number="topK" type="number" min="1" max="20" /></label>
          <label>最低分<input v-model.number="threshold" type="number" min="0" max="1" step="0.01" /></label>
        </div>
        <button class="primary-btn" :disabled="searching || !query.trim()" @click="runSearch">
          {{ searching ? '检索中...' : '运行检索测试' }}
        </button>
        <p v-if="error" class="error">{{ error }}</p>
        <div v-if="searchResult" class="search-summary">
          <span>候选 {{ searchResult.candidate_count }}</span>
          <span>命中 {{ searchResult.hits.length }}</span>
          <span>{{ searchResult.retrieval_mode }}</span>
        </div>
      </section>

      <section class="panel config-panel">
        <div class="panel-title"><div><b>RAG 运行链路配置</b><span>RAG 是检索编排流程，向量数据库只负责存储与召回</span></div></div>
        <dl>
          <div><dt>检索编排</dt><dd>{{ stats.engine || 'RAG hybrid retrieval' }}</dd></div>
          <div><dt>向量存储</dt><dd>{{ stats.vector_store || 'ChromaDB' }}</dd></div>
          <div><dt>处理链路</dt><dd>{{ stats.pipeline || 'embedding → retrieval → rerank → evidence' }}</dd></div>
          <div><dt>嵌入模型</dt><dd>{{ stats.embedding_model || '-' }}</dd></div>
          <div><dt>切分策略</dt><dd>段落感知 + 长段滑窗</dd></div>
          <div><dt>融合重排</dt><dd>Weighted Fusion</dd></div>
          <div><dt>回答约束</dt><dd>证据不足拒答 + [n] 引用</dd></div>
          <div><dt>红线处置</dt><dd>关键词阻断 / 语义命中复核</dd></div>
        </dl>
        <div class="roadmap">
          <b>主流方案对齐</b>
          <p><span>已实现</span>混合检索、重排、元数据过滤、引用溯源、单点测试</p>
          <p><span class="next">下一阶段</span>QA 拆分、可编辑分块、批量评测、FastGPT OpenAPI 适配</p>
        </div>
      </section>
    </div>

    <section v-if="searchResult" class="panel results-panel">
      <div class="panel-title"><div><b>召回证据</b><span>按融合分数排序；得分不是内容安全结论</span></div></div>
      <div v-if="!searchResult.hits.length" class="empty-result">没有证据达到当前阈值，请降低阈值或补充知识库。</div>
      <article v-for="hit in searchResult.hits" :key="hit.chunk_id" class="hit">
        <div class="rank">{{ hit.rank }}</div>
        <div class="hit-main">
          <div class="hit-head"><b>{{ hit.filename }}</b><span>{{ hit.category }} · 分块 #{{ hit.chunk_index }}</span></div>
          <p>{{ hit.snippet }}</p>
        </div>
        <div class="scores"><b>{{ Math.round(hit.score * 100) }}%</b><span>融合</span><small>向量 {{ Math.round(hit.vector_score * 100) }} · 词法 {{ Math.round(hit.keyword_score * 100) }}</small></div>
      </article>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

const stats = ref<any>({})
const query = ref('')
const category = ref('')
const topK = ref(5)
const threshold = ref(0.32)
const searchResult = ref<any>(null)
const loading = ref(true)
const searching = ref(false)
const error = ref('')

onMounted(async () => {
  try {
    const response = await fetch('/api/kb/stats')
    if (!response.ok) throw new Error('读取检索引擎状态失败')
    stats.value = await response.json()
    threshold.value = stats.value.score_threshold ?? 0.32
  } catch (reason:any) {
    error.value = reason?.message || '检索引擎不可用'
  } finally {
    loading.value = false
  }
})

async function runSearch() {
  if (!query.value.trim() || searching.value) return
  searching.value = true
  error.value = ''
  try {
    const body = new FormData()
    body.append('question', query.value.trim())
    body.append('top_k', String(topK.value))
    body.append('score_threshold', String(threshold.value))
    if (category.value) body.append('category', category.value)
    const response = await fetch('/api/kb/search', { method: 'POST', body })
    if (!response.ok) throw new Error('检索失败，请检查模型与知识库状态')
    searchResult.value = await response.json()
  } catch (reason:any) {
    error.value = reason?.message || '检索失败'
  } finally {
    searching.value = false
  }
}
</script>

<style scoped>
.rag-page{max-width:1240px;margin:0 auto;padding-bottom:32px}.page-head{display:flex;align-items:flex-start;justify-content:space-between;gap:24px;margin-bottom:18px}.eyebrow{margin:0 0 5px;color:var(--primary);font-size:11px;font-weight:700}.page-head h1{margin:0;color:var(--text);font-size:24px;font-weight:700}.page-head p:not(.eyebrow){margin:7px 0 0;color:var(--muted);font-size:13px}.health{display:flex;align-items:center;gap:7px;padding:7px 10px;border:1px solid var(--line);border-radius:6px;background:var(--surface);color:var(--muted);font-size:11px}.health i{width:7px;height:7px;border-radius:50%;background:#16a074;box-shadow:0 0 0 3px rgba(22,160,116,.12)}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:12px}.metrics article,.panel{background:var(--surface);border:1px solid var(--line);border-radius:7px}.metrics article{display:flex;flex-direction:column;gap:5px;padding:15px 17px}.metrics span{color:var(--muted);font-size:11px}.metrics b{color:var(--text);font-size:24px}.metrics .metric-text{font-size:18px}.metrics small{color:var(--muted);font-size:10px}.panel{padding:17px}.panel-title{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:15px}.panel-title b{display:block;color:var(--text);font-size:14px}.panel-title span{display:block;margin-top:4px;color:var(--muted);font-size:11px}.version{padding:4px 7px;border-radius:4px;background:rgba(8,126,174,.08);color:var(--primary)!important;font-weight:700}.pipeline{display:grid;grid-template-columns:1fr auto 1fr auto 1fr auto 1fr auto 1fr;align-items:center;gap:9px}.stage{min-height:82px;padding:12px;border:1px solid var(--line);border-radius:6px;background:var(--surface-2)}.stage strong{display:block;color:var(--primary);font-size:10px}.stage b{display:block;margin:7px 0 4px;color:var(--text);font-size:12px}.stage span{color:var(--muted);font-size:10px}.connector{color:#8ea8b7}.workspace-grid{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(300px,.75fr);gap:12px;margin-top:12px}.query-label{display:block;margin-bottom:6px;color:var(--muted);font-size:11px}.search-panel textarea,.controls select,.controls input{border:1px solid var(--line);border-radius:5px;background:var(--surface-2);color:var(--text);outline:none}.search-panel textarea{box-sizing:border-box;width:100%;padding:11px;resize:vertical;font:inherit;font-size:13px;line-height:1.6}.search-panel textarea:focus,.controls select:focus,.controls input:focus{border-color:var(--primary)}.controls{display:grid;grid-template-columns:1fr 100px 110px;gap:9px;margin:10px 0}.controls label{display:flex;flex-direction:column;gap:5px;color:var(--muted);font-size:10px}.controls select,.controls input{box-sizing:border-box;width:100%;height:34px;padding:0 9px}.primary-btn{width:100%;height:36px;border:0;border-radius:5px;background:var(--primary);color:#fff;font-weight:650;cursor:pointer}.primary-btn:disabled{opacity:.5;cursor:not-allowed}.error{color:#bf3447;font-size:11px}.search-summary{display:flex;flex-wrap:wrap;gap:7px;margin-top:10px}.search-summary span{padding:4px 7px;border-radius:4px;background:var(--surface-2);color:var(--muted);font-size:10px}.config-panel dl{margin:0}.config-panel dl div{display:grid;grid-template-columns:92px 1fr;gap:10px;padding:8px 0;border-bottom:1px solid var(--line);font-size:11px}.config-panel dt{color:var(--muted)}.config-panel dd{margin:0;color:var(--text);word-break:break-word}.roadmap{margin-top:13px;padding:11px;border-left:3px solid var(--primary);background:var(--surface-2)}.roadmap b{font-size:11px}.roadmap p{margin:7px 0 0;color:var(--muted);font-size:10px;line-height:1.5}.roadmap span{margin-right:6px;color:#147a66;font-weight:700}.roadmap .next{color:#9a6a13}.results-panel{margin-top:12px}.hit{display:grid;grid-template-columns:28px 1fr 120px;gap:12px;align-items:start;padding:12px 0;border-top:1px solid var(--line)}.rank{display:grid;place-items:center;width:26px;height:26px;border-radius:5px;background:rgba(8,126,174,.09);color:var(--primary);font-size:11px;font-weight:700}.hit-head{display:flex;align-items:center;justify-content:space-between;gap:12px}.hit-head b{color:var(--text);font-size:12px}.hit-head span{color:var(--muted);font-size:10px}.hit-main p{margin:7px 0 0;color:var(--muted);font-size:11px;line-height:1.65;white-space:pre-wrap}.scores{text-align:right}.scores b{display:block;color:var(--primary);font-size:17px}.scores span,.scores small{display:block;color:var(--muted);font-size:9px}.scores small{margin-top:5px}.empty-result{padding:20px;color:var(--muted);font-size:12px;text-align:center}@media(max-width:980px){.metrics{grid-template-columns:repeat(2,1fr)}.pipeline{grid-template-columns:1fr 1fr}.connector{display:none}.workspace-grid{grid-template-columns:1fr}}@media(max-width:620px){.rag-page{padding-bottom:18px}.page-head{flex-direction:column}.metrics{grid-template-columns:1fr}.pipeline{grid-template-columns:1fr}.controls{grid-template-columns:1fr 1fr}.controls label:first-child{grid-column:1/-1}.hit{grid-template-columns:28px 1fr}.scores{grid-column:2;text-align:left}.hit-head{align-items:flex-start;flex-direction:column;gap:3px}}
</style>
