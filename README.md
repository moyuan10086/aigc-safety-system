# AIGC 内容安全检测系统

基于多模态大模型与对比学习的 AIGC 内容安全检测研究及其应用

## 系统架构

```
aigc-safety-system/
├── backend/              # FastAPI 后端
│   ├── services/         # 三大检测服务
│   │   ├── deepfake_service.py    # CLIP Deepfake 检测
│   │   ├── mllm_service.py        # MLLM 可解释性检测
│   │   └── rag_service.py         # RAG 内容安全审核
│   ├── routers/          # API 路由
│   ├── config.py         # 配置
│   └── main.py           # 入口
└── frontend/             # Vue3 前端
    ├── src/views/
    │   ├── Detect.vue    # 检测页面
    │   └── Report.vue    # 报告页面
    └── dist/             # 构建产物
```

## 核心功能

### 1. Deepfake 检测（第三章）
- 基于 CLIP 视觉编码器 + LN-tuning
- 调用 `deepfake-detection/` 训练好的模型
- 返回：真实/伪造标签、置信度、得分

### 2. MLLM 可解释性检测（第四章）
- 通过 OpenAI 兼容接口调用多模态大模型
- 支持 GPT-4o / Claude Opus 4.6 / Gemini 3.1 Pro
- 返回：判断结果、证据列表、可疑区域、中文解释

### 3. RAG 内容安全审核（第五章）
- ChromaDB 向量数据库 + 敏感词库
- 混合检索：关键词匹配 + 语义相似度
- 返回：安全状态、命中关键词、违规规则、风险等级

### 4. SSE 流式审计报告（第六章）
- `/api/detect/full` 接口
- 实时推送三个模块的检测进度和结果
- 前端 EventSource 接收流式数据

### 5. 大模型与 Agent 双层安全护栏
- Qwen3Guard：通用内容安全、中文风险与越狱分类
- SingGuard-NSFA：危险工具调用、资源滥用、敏感信息和 Agent 操作风险
- 输入预检、真实模型生成、输出复检与高风险隔离
- 两个模型均为可选专家；不可用时保留规则/RAG 链路并在 `engine.components` 标记降级状态

## 快速开始

### 1. 配置环境

```bash
# 复制配置文件
cp backend/.env.example backend/.env

# 编辑 backend/.env，填入 API Key
MLLM_API_KEY=your_api_key
MLLM_BASE_URL=https://api.openai.com/v1
MLLM_MODEL=gpt-4o
```

### 2. 启动系统

**Windows:**
```bash
start.bat
```

**手动启动:**
```bash
# 构建前端
cd frontend && npm run build && cd ..

# 启动后端
cd backend && uv run main.py
```

访问：http://localhost:8010

## 服务器部署

比赛演示服务器采用单进程 FastAPI + systemd，前端静态文件由 FastAPI 同源托管。生产环境不要使用 `main.py` 中的热重载开发入口。

```bash
# 代码目录
/root/CH/aigc-safety-system

# 首次部署（先准备 backend/.env；脚本会自动下载模型）
bash deploy/bootstrap.sh

# 后续从 GitHub 更新
bash deploy/update.sh

# 查看状态与日志
systemctl status aigc-safety.service
journalctl -u aigc-safety.service -f
```

服务默认监听 `0.0.0.0:8010`，健康检查为 `GET /api/health`。模型权重、API 密钥、上传文件、报告和向量数据库均被 Git 忽略，不会推送到 GitHub。

### GPU 护栏服务

SingGuard 使用独立 Transformers 5 环境，避免与要求 `transformers<5` 的 vLLM 环境冲突：

```bash
python -m venv --system-site-packages /mnt/data/singguard/env
/mnt/data/singguard/env/bin/pip install -r deploy/gpu/requirements-singguard.txt
bash deploy/gpu/start_singguard.sh
```

主系统通过以下环境变量启用两个远程分类专家。密钥只写入服务器的 `backend/.env`，不要提交到 Git：

```bash
GUARDRAIL_ENABLE_QWEN_CLASSIFIER=true
GUARDRAIL_QWEN_BASE_URL=http://GPU_HOST:18200/v1
GUARDRAIL_QWEN_MODEL=qwen3guard-gen-0.6b
GUARDRAIL_QWEN_API_KEY=server_managed_secret

GUARDRAIL_ENABLE_SINGGUARD_CLASSIFIER=true
GUARDRAIL_SINGGUARD_BASE_URL=http://GPU_HOST:18210/v1
GUARDRAIL_SINGGUARD_MODEL=singguard-nsfa-0.8b
GUARDRAIL_SINGGUARD_API_KEY=server_managed_secret
```

可复现实测命令：

```bash
python scripts/benchmark_singguard.py \
  --base-url http://127.0.0.1:18210/v1 \
  --api-key-file /mnt/data/singguard/api-key \
  --output docs/evidence/singguard-benchmark-20260802.json
```

RTX 4090 生成式模式实测为 10 例中 9 例正确，平均 5354.2 ms、P95 7830.5 ms。该结果是小样本工程冒烟测试，不等价于论文基准；完整系统使用规则、RAG、Qwen3Guard 与 SingGuard 并联融合补充单模型漏报。

## API 文档

### 对外 API v1（API Key 鉴权）

审核员登录后可在“系统设置 → 开放 API 与租户”签发和撤销 API Key。服务端只保存 HMAC-SHA256 摘要，明文密钥仅在签发响应中出现一次。调用方可使用 `Authorization: Bearer <key>` 或 `X-API-Key: <key>`。

```bash
# 输入/输出护栏
curl -X POST https://aigc.49.51.248.227.sslip.io/api/v1/guardrail/check \
  -H "Authorization: Bearer <api-key>" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"正常的产品咨询","response":"","mode":"input"}'

# 当前 Key 的用量、成功率与配额
curl https://aigc.49.51.248.227.sslip.io/api/v1/usage?days=7 \
  -H "X-API-Key: <api-key>"

# 提交受控主动扫描（异步返回 202）
curl -X POST https://aigc.49.51.248.227.sslip.io/api/v1/scans \
  -H "X-API-Key: <api-key>" -H "Content-Type: application/json" \
  -d '{"preset":"quick"}'

# 查询本 Key 的扫描与报告，并下载脱敏 JSON 报告
curl https://aigc.49.51.248.227.sslip.io/api/v1/scans/<scan-id> -H "X-API-Key: <api-key>"
curl https://aigc.49.51.248.227.sslip.io/api/v1/reports/<report-id>/download -H "X-API-Key: <api-key>" -o report.json
```

统一成功响应包含 `api_version`、`request_id` 和 `data`。当前 v1 能力包括：

- `POST /api/v1/guardrail/check`：输入/输出双向审核
- `POST /api/v1/guardrail/chat`：实际生成模型 + 输入输出护栏
- `POST /api/v1/content/check`：红线知识与敏感内容审核
- `POST /api/v1/images/face`：人脸与图像质量检查
- `POST /api/v1/images/deepfake`：Deepfake 检测
- `POST /api/v1/images/mllm`：多模态图片审核
- `GET /api/v1/catalog`：当前 Key 的作用域与配额
- `GET /api/v1/usage`：当前 Key 的调用量与延迟
- `POST /api/v1/scans`、`GET /api/v1/scans[/{id}]`：提交和查询租户隔离的异步 garak 扫描（仅 quick/standard）
- `POST /api/v1/reports`、`GET /api/v1/reports[/{id}]`、`GET /api/v1/reports/{id}/download`：从已完成扫描生成、查询和下载租户隔离报告

每个 Key 绑定租户、作用域、每分钟限流和每日配额；调用账本不保存提示词或模型输出。原始提示词与危险模型输出仍按审计策略写入独立 AES-GCM 加密证据库。

### 维护、备份与密钥轮换

维护命令只在服务器本地执行，不暴露为公网 API。在线备份会同时保存审计库和 API Key/租户账本，生成带 SHA-256 文件校验、事件数量、证据数量和哈希链状态的 `manifest.json`；默认只归档不删除生产证据。

```bash
cd /root/CH/aigc-safety-system/backend
uv run python maintenance.py backup --label before-release
uv run python maintenance.py verify --archive <manifest-archive-name>
```

API Key 哈希轮换：先把新值写入 `API_KEY_HASH_SECRET`，旧值暂存到 `API_KEY_HASH_PREVIOUS_SECRET` 并重启；旧 Key 首次使用时惰性迁移为新摘要。确认宽限期结束且调用方已更新后，再清空上一密钥。AES-GCM 证据轮换同样先配置 `AUDIT_CONTENT_KEY` 新值和 `AUDIT_CONTENT_PREVIOUS_KEY` 旧值，然后执行：

```bash
uv run python maintenance.py rotate-evidence
```

### 中文护栏回归与 XGBoost 影子评测

`evaluations/` 使用 promptfoo 对 `/api/guardrail/check` 执行输入侧、输出侧中文安全回归。该套件默认关闭所有远程分类器，不读取任何生产密钥：

```bash
cd backend
GUARDRAIL_ENABLE_RAG=false uv run uvicorn offline_guardrail_app:app --app-dir ../evaluations --host 127.0.0.1 --port 18080
cd ../evaluations
npm ci
npm run eval:guardrail
```

本地交付包可作为影子评测器并行运行，但不会改变在线 `safe/borderline/unsafe` 结果。模型使用 pickle 载荷，只有可信文件才可启用；系统在加载前强制校验 SHA-256：

```bash
GUARDRAIL_ENABLE_XGBOOST_SHADOW=true
GUARDRAIL_XGBOOST_SHADOW_MODULE_PATH=/opt/aigc-local-auditor
GUARDRAIL_XGBOOST_SHADOW_MODEL_PATH=/opt/aigc-local-auditor/security_audit_system/models/hybrid_safety_model_xgboost_color.json
GUARDRAIL_XGBOOST_SHADOW_SHA256=<64位模型摘要>
```

影子输出只包含决策、置信度、一致性、耗时和模型摘要；原始提示词与模型危险输出仍只保存在 AES-GCM 加密的 `audit_evidence`，不会进入 API 用量、CSV 导出或租户报告。

数据驾驶舱的“人工复核样本池”只接纳同时具备护栏主判和加密证据的真实事件。队列优先展示主判/影子模型分歧，再按 `safe`、`borderline`、`unsafe` 分层抽样；200 条目标只统计已登录审核员实际提交的标签，不使用合成标签补数。`GET /api/dashboard/review-labels.csv` 可导出事件哈希、主判、人工标签、类别与复核人等元数据，不解密或导出原始提示词及模型危险输出。

人工复核默认使用盲审模式隐藏主判与影子结果。审核员必须先通过取证详情解密原始证据，形成与事件 ID、审核员身份绑定的 `audit.evidence_access` 审计事件，随后才能提交标签；其他审核员的证据访问记录不能代为解锁。导出的标签元数据包含 `evidence_access_verified`，用于证明标签具备“本人先审证据、后给真值”的审计链依据。

多人复核使用 `POST /api/dashboard/review-claims/{event_id}` 原子领取样本，默认租约为 15 分钟；他人的未过期租约不能抢占。每次新领取后必须重新查看证据，历史 `evidence_access` 不能复用。首次人工标签写入后不可覆盖，完成一条时系统会原子领取并打开下一条可用样本。领取和自动流转均写入 `guardrail.review_claim` 审计事件，CSV 同时导出 `review_claim_verified` 与 `evidence_access_verified`，仍不包含原始提示词或危险输出。

该命令会先生成并校验轮换前备份，再重加密全部证据；没有两把密钥时会拒绝执行。原始提示词和危险模型输出始终保留在加密证据表，列表、用量账本、报告摘要和 CSV 不返回原文。

### 单独检测接口

**Deepfake 检测**
```bash
POST /api/detect/deepfake
Content-Type: multipart/form-data
Body: image=<file>

Response: {"score": 0.85, "label": "fake", "confidence": 0.70}
```

**MLLM 检测**
```bash
POST /api/detect/mllm
Content-Type: multipart/form-data
Body: image=<file>

Response: {
  "verdict": "fake",
  "confidence": 0.9,
  "evidence": ["不自然的面部边缘", "光照不一致"],
  "regions": ["眼睛周围", "嘴部"],
  "explanation": "该图像存在明显的AI生成痕迹..."
}
```

**内容安全审核**
```bash
POST /api/detect/content
Content-Type: application/x-www-form-urlencoded
Body: text=<content>

Response: {
  "safe": false,
  "matched_keywords": ["暴力", "血腥"],
  "violated_rules": ["禁止暴力血腥内容"],
  "risk_level": "high"
}
```

### 全量审计接口（SSE）

```bash
POST /api/detect/full
Content-Type: multipart/form-data
Body: image=<file>&text=<content>

Response: text/event-stream
event: step
data: {"step": "deepfake", "status": "running"}

event: deepfake
data: {"score": 0.85, "label": "fake", "confidence": 0.70}

event: step
data: {"step": "mllm", "status": "running"}

event: mllm
data: {"verdict": "fake", "confidence": 0.9, ...}

event: step
data: {"step": "rag", "status": "running"}

event: rag
data: {"safe": true, "risk_level": "low"}

event: done
data: {"status": "completed"}
```

## 技术栈

**后端:**
- FastAPI — 异步 Web 框架
- PyTorch + CLIP — Deepfake 检测
- OpenAI SDK — MLLM 调用
- ChromaDB — 向量数据库
- Sentence-Transformers — 文本嵌入

**前端:**
- Vue 3 + TypeScript
- Element Plus — UI 组件库
- Vite — 构建工具
- EventSource — SSE 客户端

## 论文对应关系

| 章节 | 模块 | 代码位置 |
|------|------|----------|
| 第三章 | CLIP Deepfake 检测 | `services/deepfake_service.py` |
| 第四章 | MLLM 可解释性检测 | `services/mllm_service.py` |
| 第五章 | RAG 内容安全审核 | `services/rag_service.py` |
| 第六章 | 系统集成与工程化 | `main.py` + `routers/detect.py` |
| 第六章 | Vue3 前端界面 | `frontend/src/` |
| 第六章 | SSE 流式审计报告 | `routers/detect.py:full_audit()` |

## 依赖项目

- `../deepfake-detection/` — CLIP 模型训练与推理
- `../mllm-defake/` — MLLM 检测框架（参考）
- `../数字人前端/backend/Sensitive-lexicon/` — 敏感词库

## 开发者

陈昊 - 广东技术师范大学 - 2026届本科毕业设计
