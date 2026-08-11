# AIGC 图片与人脸审核平台：评测与证据总报告

更新时间：2026-08-09

对应飞书总文档：<https://my.feishu.cn/docx/Z1OndNtyzoTk6WxyjjccOX0hnXc>（当前浏览器显示“登录/注册”，本次未直接写入）。

## 1. 平台结论口径

平台将真实性、内容安全和来源取证分开呈现：

- Deepfake：显示模型输出的 `P(fake)`，它是模型分数，不是准确率；`P(fake) >= 0.50` 为当前处置阈值。
- 图片内容安全：每个安全类别独立给出 confidence，综合风险取模型风险和命中类别的最大值；`>= 0.80` 阻断，`0.35-0.79` 人工复核，低于 `0.35` 安全。
- RAG：输出红线等级和命中证据，不与 Deepfake 概率相加。
- C2PA/IPTC/隐写水印：属于来源证据，不能单独证明图片真实、AI 生成或安全。

### RAG 误报回归

真实审核报告曾发现英文通用词被敏感词库按子串误命中：
`This is a benign safety review demonstration.` 被错误识别为 `IS` 和 `this`。
现已改为 ASCII 词边界匹配，并过滤通用停用词；中文词条仍按短语匹配。
修复后的线上结果为 `safe / low / allow`，证据见
`docs/evidence/rag-keyword-boundary-regression-20260809.json`。

### PII 图像安全扩展 smoke

已使用公开 MIT 仓库 `YoutingWang/MM-SafetyBench` 的 5 张合成 PII 正类与 25 张 OCR 注入负类进行真实 MLLM 推理。脱敏证据见 `docs/evidence/mm-safetybench-pii-ocr-30-evidence-20260809.json`，统计输出见 `docs/evidence/content-safety-personal-data-statistical-evaluation-30-20260809.json`。在该数据域和 one-vs-rest 任务定义下，30 条样本得到 Accuracy 0.9333（Wilson 95% CI 0.7868–0.9815）、ROC-AUC 0.9840（bootstrap 95% CI 0.9366–1.0000）、PR-AUC 0.9429、Brier 0.0474、ECE 0.0737，阈值为 0.5。该结果只支持“该公开合成数据协议内的扩展任务指标”，不代表通用现实世界 PII 检测能力，也不能外推为核心五类内容安全任务或 SOTA。

评测证据不保存本机绝对路径；机器可读报告记录 manifest 文件名、manifest SHA-256、数据集、split、模型版本和标签来源。审核页同步展示这些协议字段，长模型标识仅在卡片内截断，完整值可通过悬停查看。

## 2. 审核页 UI

正式站 `/detect` 已完成部署验证：

- 顶部为“样本概览 / 审核能力 / 核心结论”。
- 核心结论为“伪造风险 / 内容安全 / 解释证据”。
- 检测能力明确区分人脸伪造、多模态解释、红线知识库检索、图片内容安全。
- 桌面 1440×1000、移动 390×844 均完成回归，无横向溢出。
- Deepfake 结果标注“模型分数，非准确率”。

## 3. 统计评测器

评测输入是独立、人工标注、版本冻结的 `heldout.jsonl`。每个 `task` 独立计算：Accuracy/Wilson 95% CI、Precision、Recall、F1、ROC-AUC、PR-AUC、Brier、ECE，以及主要指标的 bootstrap 95% CI。

样本少于 30 或任一类别少于 5 时固定返回 `insufficient_samples`，禁止发布统计校准结论。

## 4. 已完成真实实验

### DF40 派生数据集：带标签统计评测

在不参与训练的独立 validation/test split 上运行第三方 CLIP-LN checkpoint，两个 split 各 3,012 张，fake/real 各 1,506 张。评测器计算 Accuracy（Wilson 95% CI）、ROC-AUC（bootstrap 95% CI）、PR-AUC、Brier 和 ECE；结果只描述本 checkpoint 与本预处理协议。

| split | Accuracy（95% CI） | ROC-AUC（95% CI） | PR-AUC | Brier | ECE |
|---|---:|---:|---:|---:|---:|
| validation | 0.8805（0.8684–0.8916） | 0.9537（0.9461–0.9616） | 0.9641 | 0.0925 | 0.1074 |
| test | 0.7198（0.7035–0.7355） | 0.8812（0.8682–0.8938） | 0.8912 | 0.1839 | 0.1670 |

这组结果支持“在该公开派生数据集协议上完成统计评测”，不支持“通用准确率”或无协议 SOTA 宣称。验证集选择的阈值为 0.29，必须锁定后再报告测试集，不能根据测试集调阈值。机器可读证据：`docs/evidence/df40-statistical-evaluation-20260809.json`。

### 图片内容安全公开数据集评测

已下载并冻结三个公开数据集的具体提交版本，原图仅保存在服务器评测缓存，不进入 Git、前端静态目录或飞书。统一测试集共 75 张：15 张步枪、15 张雨伞难负样本、15 张暴力、15 张非暴力、15 张成人内容合成图。每张图只调用一次真实多模态模型，同时输出成人、武器和暴力三类分数，共形成 225 条 held-out 记录。

| 任务 | 样本（正/负） | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---|---:|---:|---:|---:|---:|---:|
| 成人内容 | 75（15/60） | 0.8000 | 0.0000 | 0.0000 | 0.0000 | 0.5000 |
| 暴力 | 75（15/60） | 0.7867 | 0.4706 | 0.5333 | 0.5000 | 0.6606 |
| 武器展示 | 75（15/60） | 0.8533 | 0.5769 | 1.0000 | 0.7317 | 0.9500 |

成人内容的 80% Accuracy 完全由 60 个负样本撑起，15 个阳性全部漏报，因此该任务当前不可用于自动放行，必须标记为“统计完成、召回偏低”并进入人工复核。暴力任务召回率 53.33%，仍需扩充数据与优化策略；武器任务在本冻结集上召回率 100%，但存在 11 个误报，精确率为 57.69%。

公开数据来源：`Simuletic/CCTV_Weapon_Detection_Rifles_vs_Umbrellas`（CC BY-NC 4.0）、`farazv2/violence-detection-violence-class`（MIT）、`Anik121/NSFW_Image`（MIT）。政治敏感和营销违规没有找到同时满足许可证清晰、真值标签与平台业务口径一致的数据集，仍保持未校准，禁止用相近图片硬映射。

证据：`docs/evidence/public-content-safety-acquisition-20260809.json`、`docs/evidence/public-content-safety-model-evidence-20260809.json`、`docs/evaluation/public-content-safety-heldout-20260809.jsonl`、`docs/evidence/public-content-safety-statistical-evaluation-20260809.json`。旧的 `detection-score-smoke-20260809.json` 仅保留为链路冒烟记录，不再覆盖三类正式统计结果。

### FaceForensics 盲测

- 1000 张公开 benchmark PNG，数据包 SHA-256：`eb7494e0ea0d8e20603b57b5066bc1f13437062771d6b4f0f6b4c26ea786e4d0`。
- RTX 4090 GPU0 推理 30.0146 秒，吞吐 33.3171 张/秒。
- 平均 `P(fake)=0.1668`，中位数 `0.0933`，91 张超过 0.50。
- 压缩包不含真值标签，当前不能计算 Accuracy/AUC/PR-AUC。

证据：`docs/evidence/faceforensics-blind-predictions-20260809.json`。

## 5. 官方提交产物

已按官方格式生成 `faceforensics-submission-20260809.zip`：解压后只有 `predictions.json`，包含 1000 个文件名到 `fake/real` 的映射。SHA-256：`57c5fac59ec3538be712b93bb5994100a150a87d9c142ace432305415ee5f178`。

状态为 `prepared_not_submitted`。官方要求测试集只提交最终版本一次，因此需要负责人登录后确认提交，不由平台自动提交。

## 6. 公开数据与许可

- GenImage：CC BY-NC-SA 4.0 及附加 Dataset Terms，当前只登记元数据。
- FaceForensics++：数据需官方申请和 Terms of Use；盲测 benchmark 已合法下载到项目外缓存。
- Synthbuster 旧仓库链接已确认不存在，暂不引用。

审计：`docs/evaluation/dataset-access-audit-20260809.json`。

## 7. 后续人工动作

1. 负责人登录官方 FaceForensics benchmark 页面，确认一次性提交政策。
2. 上传已校验的提交包，保存 submission ID 和官方评分回执。
3. 将官方各类别分数、提交时间、模型哈希写入本报告。
4. 获取带真值标签的公开 test split 后，再运行校准评测器并生成 bootstrap CI。
