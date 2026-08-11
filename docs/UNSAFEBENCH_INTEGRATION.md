# UnsafeBench 实际模型接入

平台接入的是 UnsafeBench 生态中的图像安全专家模型，不把评测仓库误当成在线审核 API。现有主链路仍由 MLLM 内容安全模型负责，UnsafeBench 作为 `specialist_evidence.unsafe_bench` 影子证据并列返回。

## GPU 推理服务契约

在 4090/NPU 机器启动模型服务后，将 `UNSAFE_BENCH_ENDPOINT` 指向以下接口：

```http
POST /infer
Content-Type: multipart/form-data
file=<image>
X-Content-SHA256=<sha256>
```

响应必须是 JSON：

```json
{
  "verdict": "safe|review|unsafe",
  "risk_score": 0.0,
  "category_scores": {"sexual": 0.0, "violence": 0.0, "spam": 0.0},
  "categories": ["sexual", "violence"]
}
```

当前统一 taxonomy 为 sexual、violence、hateful、shocking、self_harm、political、illegal_activity、deception、spam、harassment、health。模型只返回自己支持的类别即可；缺失类别不补零。`unsure/uncertain` 必须映射为 `inconclusive`，进入人工复核，不允许随机分配为 safe 或 unsafe。

适配器会把结果统一为 `detected / not_detected / inconclusive / not_configured`。网络超时、5xx、无端点和非法 JSON 都是 `inconclusive`，不会降级成“安全”。

## 配置

```env
UNSAFE_BENCH_ENABLED=true
UNSAFE_BENCH_ENDPOINT=http://<GPU-SERVICE>:8000/infer
UNSAFE_BENCH_MODEL=multiheaded
UNSAFE_BENCH_TIMEOUT_SECONDS=30
```

UnsafeBench 结果不覆盖 Deepfake、C2PA、NudeNet 或主内容安全结论，最终处置仍需要规则和人工复核共同决定。
