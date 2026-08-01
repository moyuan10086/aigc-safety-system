<template>
  <div class="page">
    <div class="card">
      <div class="card-title">红线策略与检索引擎</div>
      <div class="section">
        <div class="section-label">向量数据库</div>
        <div class="info-rows">
          <div class="info-row"><span class="k">引擎</span><span class="v">ChromaDB</span></div>
          <div class="info-row"><span class="k">嵌入模型</span><span class="v">paraphrase-multilingual-MiniLM-L12-v2</span></div>
          <div class="info-row"><span class="k">数据库路径</span><span class="v">./rag_db</span></div>
          <div class="info-row"><span class="k">词库路径</span><span class="v">Sensitive-lexicon/Vocabulary</span></div>
        </div>
      </div>
      <div class="section">
        <div class="section-label">检索策略</div>
        <div class="info-rows">
          <div class="info-row"><span class="k">关键词红线</span><span class="badge badge-success">强阻断</span></div>
          <div class="info-row"><span class="k">向量相似度</span><span class="badge badge-success">人工复核</span></div>
          <div class="info-row"><span class="k">相似度阈值</span><span class="v">0.5</span></div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page { max-width: 800px; margin: 0 auto; }
.section { margin-top: 16px; }
.section-label { font-size: 11px; color: var(--primary); font-weight: 600; margin-bottom: 8px; }
.info-rows { display: flex; flex-direction: column; gap: 8px; }
.info-row { display: flex; align-items: center; gap: 12px; font-size: 13px; padding: 10px 0; border-bottom: 1px solid var(--line); }
.k { color: var(--muted); width: 140px; flex-shrink: 0; }
.v { color: var(--text); font-weight: 500; font-family: monospace; font-size: 12px; word-break:break-word; }
.badge { display: inline-flex; padding: 3px 9px; border-radius: 4px; font-size: 10px; font-weight: 600; }
.badge-success { background: rgba(52,211,153,.1); color: var(--success); }
</style>
