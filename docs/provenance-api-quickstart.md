# C2PA 对外 API 快速手册

接口：`POST /api/v1/images/provenance/verify`

## 1. 申请权限

由系统管理员在登录后的 API Key 页面签发租户 Key，并勾选 `image:provenance` scope。Key 只在签发响应中显示一次，调用方应放入服务端密钥管理，不要放进浏览器、飞书、截图、Git 或普通日志。

## 2. 调用示例

```bash
curl -X POST \
  -H "Authorization: Bearer ${AIGC_API_KEY}" \
  -F "image=@public-sample.jpg;type=image/jpeg" \
  https://aigc.49.51.248.227.sslip.io/api/v1/images/provenance/verify
```

响应为 v1 envelope，返回 request_id、四态 overall_state、Content Credentials 安全摘要、SHA-256 和 `raw_image_retained=false`。完整 manifest、原始图片、密钥、原始提示词和危险模型输出不会出现在普通响应。

## 3. 错误与边界

- 未提供 Key：HTTP 401。
- Key 没有 `image:provenance`：HTTP 403。
- 非法或超限图片：按上传安全策略返回 415/413/422。
- C2PA 解析失败：HTTP 200，但 `overall_state=inconclusive`，不能当成“无来源”。
- 没有 manifest：`overall_state=not_found`，不能推断“不是 AI”。
- 有效凭证：`confirmed_source` 只说明存在可验证来源/编辑历史，不单独证明 AI 生成。
- 验证失败、资产绑定无效或不可信：`overall_state=invalid_or_tampered`，必须提升风险并转人工复核。
- 平台历史兼容的 `aigc_safety_provenance` 本地标记是未签名声明，只返回 `inconclusive` 和 `trust_verified=false`，不能伪装成 C2PA 来源确认。

本接口只做来源证据核验，不替代 Deepfake、MLLM、RAG 或人工审核。
