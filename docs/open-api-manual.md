# AIGC 安全运营台开放 API 手册

版本：2026-08-05

基础地址：`https://aigc.49.51.248.227.sslip.io`

## 1. 认证与租户隔离

管理员或审核员登录后，在“系统设置 → 开放 API 与租户”签发 API Key。调用使用以下任一请求头：

```http
Authorization: Bearer <api-key>
X-API-Key: <api-key>
```

明文 Key 仅在签发响应中显示一次。调用方必须将其放在服务端密钥管理中，不得写入浏览器前端、移动端包、飞书、截图、Git 或普通日志。服务端按 `tenant_id`、scope、每分钟限流和每日配额隔离。

所有 v1 成功响应使用统一信封：

```json
{
  "api_version": "v1",
  "request_id": "4dd5c15c66274074957b5f1e55e619c0",
  "data": {}
}
```

## 2. 接口目录

| 接口 | Scope | 说明 |
|---|---|---|
| `POST /api/v1/guardrail/check` | `guardrail:check` | 输入、输出或双向审核 |
| `POST /api/v1/guardrail/chat` | `guardrail:chat` | 实际生成模型 + 输入/输出护栏 |
| `POST /api/v1/guardrail/agent/check` | `guardrail:agent` | Agent 工具执行前门禁 |
| `POST /api/v1/guardrail/agent/result/check` | `guardrail:agent` | 工具结果回传复检 |
| `POST /api/v1/guardrail/agent/trajectory/check` | `guardrail:agent` | 多步轨迹污染和授权绕过检测 |
| `POST /api/v1/content/check` | `content:check` | 红线知识与敏感内容审核 |
| `POST /api/v1/images/face` | `image:face` | 非身份化人脸存在性、数量和质量 |
| `POST /api/v1/images/deepfake` | `image:deepfake` | Deepfake 检测 |
| `POST /api/v1/images/mllm` | `image:mllm` | 多模态图片解释 |
| `POST /api/v1/images/content-safety` | `image:content-safety` | 图片成人、武器、暴力、涉政、营销等多标签审核 |
| `POST /api/v1/images/provenance/verify` | `image:provenance` | C2PA / Content Credentials 来源验证 |
| `GET /api/v1/catalog`、`GET /api/v1/usage` | `usage:read` | 能力、配额和调用统计 |
| `/api/v1/scans` | `scan:run` / `scan:read` | 租户隔离主动扫描 |
| `/api/v1/reports` | `report:write` / `report:read` | 报告生成、查询与下载 |

## 3. 护栏检查

请求字段：

- `prompt`：字符串，最多 12000 字符。
- `response`：字符串，最多 12000 字符。
- `mode`：`input`、`output` 或 `both`。
- `prompt` 和 `response` 至少一个包含非空白文本。

```bash
curl -X POST https://aigc.49.51.248.227.sslip.io/api/v1/guardrail/check \
  -H "Authorization: Bearer ${AIGC_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"请介绍公开产品的安全能力","response":"","mode":"input"}'
```

正式站 2026-08-04 实际结果：HTTP 200，`verdict=safe`、`risk_score=0`、`risk_code=GR-ALLOW`。

调用方必须至少读取 `verdict`、`decision`、`risk_level`、`risk_score`、`categories`、`risk_code` 和 `action`。`borderline` 必须转人工复核，不能按 safe 放行。

## 4. 真实模型对话

请求字段：

- `prompt`：1–4000 字符。
- `max_tokens`：64–1200，可省略。

```bash
curl -X POST https://aigc.49.51.248.227.sslip.io/api/v1/guardrail/chat \
  -H "Authorization: Bearer ${AIGC_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"请用两句话介绍 AIGC 安全审核平台的作用","max_tokens":128}'
```

正式站 2026-08-04 实际结果：

- HTTP 200，`status=completed`。
- `model_called=true`，模型 `gpt-5.6-sol`。
- 输入、输出、最终三段 verdict 均为 `safe`。
- API 测试生成耗时 2847 ms，共 241 tokens。
- 临时测试 Key 在调用后已撤销。

只有 `model_called=true` 时才能声称实际调用生成模型。调用方还必须检查 `input_guard`、`output_guard` 和 `final_guard`，不能只展示模型文本。

## 5. 图片与 C2PA

图片接口使用 `multipart/form-data`，字段名固定为 `image`：

```bash
curl -X POST https://aigc.49.51.248.227.sslip.io/api/v1/images/provenance/verify \
  -H "X-API-Key: ${AIGC_API_KEY}" \
  -F "image=@public-sample.jpg;type=image/jpeg"
```

仅接收 JPG、PNG、WebP，并遵守 12 MiB 和像素上限。不要上传无授权真实人脸。

C2PA 四态：

| 状态 | 含义 | 调用方动作 |
|---|---|---|
| `confirmed_source` | 验证通过的来源链 | 与内容检测综合判断；不等于一定由 AI 生成 |
| `not_found` | 没找到兼容凭证 | 继续内容检测；不等于“非 AI” |
| `inconclusive` | 解析不可用、证据不足或只有未签名声明 | 转人工复核 |
| `invalid_or_tampered` | 验证失败、不可信或疑似篡改 | 提升风险并转人工复核 |

后两种状态仍可能返回 HTTP 200，它们是业务结果，不是可忽略的接口失败。

### 图片内容安全

`POST /api/v1/images/content-safety` 实际调用视觉大模型，和 `/images/mllm` 的 AI 生成/Deepfake 解释是两个不同任务。请求字段同样为 `image`：

```bash
curl -X POST https://aigc.49.51.248.227.sslip.io/api/v1/images/content-safety \
  -H "X-API-Key: ${AIGC_API_KEY}" \
  -F "image=@synthetic-risk-sample.jpg;type=image/jpeg"
```

返回字段包括 `verdict`（`safe/review/unsafe`）、`risk_score`、`categories[]`、`summary`、`requires_human_review` 和 `policy_version`。当前类别白名单为成人内容、武器展示、暴力血腥、政治敏感、营销违规、违法活动、自伤风险、未成年人风险和个人敏感信息。模型生成的未知类别会被丢弃；JSON 无法解析时固定转 `review`，不得自动放行。

2026-08-05 本地真实模型测试：成人夜店边界样本 `review/0.55`，武器展示 `review/0.95`，虚构政治集会 `review/0.72`，保证收益营销 `unsafe/0.95`；非血腥冲突后现场返回 `safe/0.05`，作为待人工复核的弱正/漏检案例保留。完整哈希、延迟和模型输出见 `docs/evidence/image-content-safety-local-20260805.json`。

同日生产实测使用独立图片模型 `gpt-5.4-mini`：保证收益营销图返回 `review/0.98` 并完整结束 SSE；Image2 合成证件被 Deepfake 误判为真实、MLLM 判不确定，但内容安全链以个人敏感信息 `0.99` 阻断。生产输入输出与失败尝试见 `docs/evidence/image-content-safety-production-20260805.json`。文本生成模型仍为 `gpt-5.6-sol`，不能把两条模型链混写成同一个模型。

## 6. Agent 护栏

`agent/check` 的核心字段为 `tool_name`、`resource`、`arguments` 和可选 `approval_token`。高风险动作必须先取得短时、一次性、精确动作授权，授权不得跨工具、资源或参数复用。

`agent/result/check` 在上述字段基础上增加 `output`（1–12000 字符）。工具执行结果必须回传复检，以识别间接提示注入、越权数据和敏感信息外泄。

轨迹检查使用 `objective`、可选 `session_id` 和 2–12 个 `steps`。每一步 `type` 为 `message`、`action` 或 `result`，禁止传入未定义字段。

## 7. 错误码、超时与重试

| HTTP | 含义 | 处理 |
|---|---|---|
| 400 | 参数或业务请求错误 | 修正请求，不自动重试 |
| 401 | 缺少或无效 Key | 检查密钥注入和是否撤销 |
| 403 | scope 不足 | 重新签发最小权限 Key |
| 413 | 图片体积超限 | 压缩或更换样本 |
| 415 | 文件类型不支持 | 使用真实 JPG/PNG/WebP |
| 422 | 字段、图像或尺寸校验失败 | 按响应 detail 修正 |
| 429 | 每分钟限流或每日配额耗尽 | 遵守 `Retry-After`，指数退避 |
| 502/503/504 | 模型或上游暂时不可用 | 最多重试 2 次；仍失败则降级或转人工 |

建议连接超时 5 秒、读取超时 120 秒。只对 429、502、503、504 做最多 2 次指数退避。生成、扫描、报告创建等写操作不要无条件重试；保存 `request_id`，先查询结果再决定是否重放。

## 8. 日志与隐私边界

- 普通日志、驾驶舱、CSV 和飞书只记录请求 ID、哈希、类别、状态、延迟和统计。
- 原始提示词和危险模型输出只保存在 AES-GCM 加密证据库。
- API Key、模型密钥和内部服务密钥不得进入证据截图或报告正文。
- 人脸接口不做人名识别、1:N 搜索、跨请求跟踪或 embedding 持久化。
