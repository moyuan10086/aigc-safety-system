# 公开测试集与 SOTA 对比计划

## 原则

1. 每个数据集独立报告，使用其官方 test split 或论文说明的评测协议。
2. 不把人脸 Deepfake、通用文生图和内容安全混为一个总分。
3. 对比 SOTA 时记录论文/仓库的任务定义、版本、数据划分和指标；不同数据集之间只做定性比较。
4. 下载、再分发、现场展示前逐项确认许可证、访问条件和样本敏感内容处理要求。

## 第一批候选基准

| 能力 | 公开基准 | 用途 | 对比指标 | 公开入口 |
| --- | --- | --- | --- | --- |
| 人脸 Deepfake | FaceForensics++ | 受控换脸、重演、合成任务 | AUC、ACC、EER | https://github.com/ondyari/FaceForensics |
| 人脸 Deepfake | Celeb-DF v2 | 更接近真实压缩与名人换脸 | AUC、ACC | https://github.com/yuezunli/celeb-deepfakeforensics |
| 人脸 Deepfake | DFDC | 大规模、多主体伪造场景 | ROC-AUC、PR-AUC | https://www.kaggle.com/c/deepfake-detection-challenge/data |
| 人脸 Deepfake | DeeperForensics-1.0 | 真实扰动与多级伪造质量 | AUC、EER | https://github.com/EndlessSora/DeeperForensics-1.0 |
| 通用 AIGC 图像 | GenImage | 跨生成器、跨域泛化 | ACC、AUC、AP | https://github.com/GenImage-Dataset/GenImage |
| 通用 AIGC 图像 | Synthbuster | 不同生成器下的合成图检测 | ACC、AUC | https://github.com/sip-group/synthbuster |
| 图像内容安全 | VLGuard | 视觉越狱/有害视觉输入 | 类别 Recall、ASR、拒答质量 | https://github.com/ys-zong/VLGuard |
| 多模态安全 | MM-SafetyBench | 多模态风险与安全响应 | 每类 ASR、安全率 | https://github.com/isXinLiu/MM-SafetyBench |
| 多模态隐私与图像注入 | YoutingWang/MM-SafetyBench | OCR 注入、合成 PII 泄露 | OCR/PII Recall、拒答率、Wilson 95% CI | https://github.com/YoutingWang/MM-SafetyBench |

### MM-SafetyBench 使用边界

仓库公开说明包含 13 个场景、5,040 个文本-图像对，图像通过 Google Drive 或百度网盘单独分发；数据许可为 CC BY-NC 4.0，限定研究/非商业使用。它主要评估 MLLM 面对图像诱导安全攻击时的拒答与安全响应，不是本平台五类“图片内容安全”标签集：场景样本以攻击问题和回答安全性为核心，不能直接当作成人、武器、暴力、政治、营销五类的平衡图像分类集。因此当前只登记为“多模态安全响应基准候选”，在确认下载授权、标签定义和正负对照样本后，才能转换为本平台的 held-out 任务；未经确认不生成统计成绩。

### YoutingWang/MM-SafetyBench 使用边界

该公开仓库 README 声明 MIT 许可，提供 1,000 张合成对抗图片（500 张 OCR 注入、500 张 PII 泄露），并提供 `metadata.csv` 真值字段。它可以作为本平台“隐私泄露与图像注入”扩展任务的候选来源，但不等同于成人、武器、暴力、政治、营销五类内容安全分类；接入前仍需核对当前仓库版本、图片完整性、标签定义和正负对照协议。

## 导入映射

每个样本先转换为 `heldout.jsonl`，不复制原图到评测报告：

```json
{"sample_id":"sha256:...","task":"deepfake","label":1,"score":0.87,"dataset":"celeb-df-v2","split":"test","model_version":"clip-vit-l14"}
```

内容安全应拆成多标签任务，例如 `content_safety:weapon_display`、`content_safety:adult_content`。每个任务分别调用：

```powershell
uv run python scripts/evaluate_detection_scores.py --input ../docs/evaluation/heldout.jsonl --output ../docs/evidence/detection-score-evaluation.json
```

## SOTA 对齐输出

每次实验必须写明：数据集版本及 split、样本数与正负类比例、模型权重版本、阈值、硬件、推理时间、ROC-AUC、PR-AUC、Precision、Recall、F1、Brier、ECE 与 95% 置信区间。仅当任务样本数及类别数满足评测器要求时，页面才允许标示“统计已校准”。

## 许可核验状态

截至 2026-08-09，仓库和数据访问状态见 [`dataset-access-audit-20260809.json`](./dataset-access-audit-20260809.json)。GenImage 目前只登记元数据，FaceForensics++ 尚未获得下载授权；在授权或逐文件许可确认前，不下载、不提交原图，也不发布 benchmark 成绩。
