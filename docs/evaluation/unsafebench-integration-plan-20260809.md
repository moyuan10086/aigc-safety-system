# UnsafeBench 图像内容安全评测接入

## 官方协议核验

官方仓库：[YitingQu/UnsafeBench](https://github.com/YitingQu/UnsafeBench)。数据页：[yiting/UnsafeBench](https://huggingface.co/datasets/yiting/UnsafeBench)。数据卡记录 10,146 张安全/不安全图像，覆盖 11 类不安全内容；来源分为 LAION-5B 真实图像和 Lexica AI 生成图像。官方字段为 `safety_label`（`Safe` / `Unsafe`）、`category`、`source` 和 `image`。

数据页当前要求接受 Data Use Agreement（DUA），并提示请求处理需要 1–2 天。系统没有绕过登录、下载原图或把网页预览当作数据集；当前状态是 `metadata_only_pending_access`。

## 与平台 API 的映射

获得授权后，只读取官方 test split，并在隔离评测目录保留原图。每个样本调用现有图片审核 API，保存脱敏记录：

```json
{
  "sample_id": "sha256:<image-hash>",
  "task": "content_safety:unsafe",
  "label": 1,
  "score": 0.87,
  "dataset": "unsafebench",
  "split": "test",
  "category": "Violence",
  "source": "Lexica"
}
```

`score` 只取图片内容安全模块的综合 `risk_score`；每个类别另建 `content_safety:<category>` 任务并取对应类别 confidence。`Deepfake`、C2PA、IPTC 和 RAG 不写入同一分数列。

## 统计门槛

UnsafeBench 的总样本量足以满足评测器最低门槛，但每个类别必须核对实际 test split 数量和正负比例。每个任务独立计算 Accuracy/Wilson 95% CI、Precision、Recall、F1、ROC-AUC、PR-AUC、Brier、ECE 和 Bootstrap 95% CI。只有本地推理完成且样本哈希、模型版本、预处理和 API 版本冻结后，才把任务状态从 `pending_access` 改成 `ready`。

## 不允许的做法

- 不把 Safe/Unsafe 标签解释为违法性或现实世界危害程度的绝对真值。
- 不把 UnsafeBench 的结果和 DF40 Deepfake 结果合并成一个平台总准确率。
- 不把 DUA 数据复制到 Git、飞书、截图或正式站样本库。
- 不在获得授权前下载、展示或上传原始敏感图片。

## 本地运行器

获得授权并把官方 `test` split 导出到隔离目录后，使用
`scripts/run_unsafebench_local.py`。该脚本只读取本地 manifest，不主动联网，
也不会绕过 Hugging Face 的 DUA。每行至少包含 `sample_id`、`image_path` 和
`safety_label`（`Safe`/`Unsafe`），可选 `category`、`source` 和 `split`。

```powershell
uv run python scripts/run_unsafebench_local.py `
  --manifest /隔离目录/unsafebench-test.jsonl `
  --output docs/evidence/unsafebench-test-evidence.json `
  --heldout-output docs/evaluation/heldout.unsafebench.jsonl
```

输出仅保留标签、模型结果、延迟、策略版本和图片 SHA-256；原图不会写入
证据 JSON。随后按 `content_safety:unsafe` 和各类别任务生成 heldout JSONL，
再调用现有统计评测器：

```powershell
uv run python backend/scripts/evaluate_detection_scores.py `
  --input docs/evaluation/heldout.unsafebench.jsonl `
  --output docs/evidence/unsafebench-statistical-evaluation.json
```

生成该固定名称的统计证据后，评测状态 API 会自动读取并展示结果。样本不足、标签缺失或模型异常时保持
`insufficient_samples`/`inconclusive`，不得降级为 `not_detected` 或发布 SOTA。
