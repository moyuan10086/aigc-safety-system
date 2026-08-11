# 检测分数统计评测

在线审核输出的是模型分数或规则风险分，不等同于统计学置信度。只有在独立、人工标注、版本冻结的留出集上运行评测后，才能描述为“校准后概率”。

当前协议内统计证据为 `../evidence/df40-statistical-evaluation-20260809.json`：第三方 CLIP-LN checkpoint 在 DF40 派生 validation/test split 上分别使用 3,012 个带标签样本，报告 Wilson/Bootstrap 95% CI、ROC-AUC、PR-AUC、Brier 和 ECE。该结果只适用于记录的模型、预处理和数据划分，不代表所有数据域的通用准确率。

图片内容安全目前仍是受控 smoke，FaceForensics 公共包仍是无标签盲测；这两类状态保持 `insufficient_samples` / `unlabeled`，不能从模型输出反推真值。

## 任务格式

### 内容安全类别适配器

`scripts/run_content_safety_benchmark.py` 支持将一个已合法取得的本地图片 manifest 拆成五个独立任务：`content_safety:adult_content`、`content_safety:marketing_violation`、`content_safety:political_sensitive`、`content_safety:weapon_display` 和 `content_safety:violence`。每行必须包含人工或数据集官方提供的 `reference_labels`；脚本拒绝没有真值标签的样本，也不从模型 verdict 反推标签。

```powershell
uv run python scripts/run_content_safety_benchmark.py `
  --manifest D:\隔离评测目录\content-safety-test.jsonl `
  --output docs/evidence/content-safety-test-evidence.json `
  --heldout-output docs/evaluation/heldout.content-safety.jsonl
uv run python backend/scripts/evaluate_detection_scores.py `
  --input docs/evaluation/heldout.content-safety.jsonl `
  --output docs/evidence/content-safety-statistical-evaluation.json
```

该适配器只保留图片 SHA-256、标签、类别分数、模型版本和延迟；原图和完整供应商响应不会写入证据。只有样本量和类别最小样本数达标时，统计评测器才会返回 `ready`。

每一行 JSONL 对应一个不可重复的留出样本：

```json
{"sample_id":"df-001","task":"deepfake","label":1,"score":0.91,"model_version":"clip-vit-l14"}
{"sample_id":"cs-001","task":"content_safety:weapon_display","label":1,"score":0.95,"policy_version":"image-safety-v1"}
```

- `label`：经双人标注及仲裁后的真实标签，`1` 为该任务的正类。
- `score`：待评估模块的正类概率或风险分，范围 `[0, 1]`。
- 同一个任务的 `score` 必须具有同一语义，不能把 Deepfake 概率、MLLM 自报分和 RAG 距离混为一个评分序列。

## 运行

```powershell
cd backend
uv run python scripts/evaluate_detection_scores.py --input ../docs/evaluation/heldout.jsonl --output ../docs/evidence/detection-score-evaluation.json
```

评测器分别按 `task` 输出：准确率及 Wilson 95% 置信区间、精确率/召回率/F1/ROC-AUC/PR-AUC 及确定性 bootstrap 95% 置信区间、Brier 分数、ECE 和可靠性分箱。默认阈值为 0.50；bootstrap 随机种子固定，便于复现。

样本少于 30 或任一类别少于 5 时，结果固定为 `insufficient_samples`，不允许用于发布“准确率”或“置信度”结论。比赛展示前建议每个核心任务至少 200 个冻结留出样本，正类至少 30 个，并保留标注人、复核记录、样本哈希、模型版本和运行时间。

## OpenAI Evals 对齐

该 JSONL 任务结构可作为 OpenAI Evals 风格的评测记录：把样本、参考标签、模型输出和评分器分离，固定版本后可重复运行。当前脚本专门计算审核分数的判别性与校准性；后续可在同一任务集加入文本解释质量、拒答质量和红线证据引用完整度的判分器。
