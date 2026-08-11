# 图片内容安全模型选型与测试机核查

## 结论

现网通用多模态模型适合做宽类别理解和中文证据说明，但不能单独承担成人内容自动放行。推荐采用“专用小模型召回 + 多模态模型复核 + 人工审核”的并行链路，并保持每个模型的原始分数和版本信息，不合成为无法解释的单一准确率。

当前优先级：

1. 先强制多模态模型返回全部风险类别分数，缺项直接转人工复核。本次已经完成接口协议和失败关闭逻辑。
2. 成人内容增加 NudeNet 或 LAION CLIP NSFW Detector 作为独立召回器，先以 shadow 模式运行，不直接阻断。
3. 获取 UnsafeBench 合法访问权限后，评测 PerspectiveVision、MultiHeaded、Q16、NSFW Detector 和 NudeNet；同一冻结划分分别报告真实图片与 AI 生成图片结果。
4. 若需要覆盖政治、仇恨、自伤、欺骗、健康和垃圾营销等宽类别，优先验证 PerspectiveVision 或 UnsafeBench 的 CLIP 线性探针，不用成人检测器冒充全类别模型。

## 公开研究依据

UnsafeBench（Qu 等，arXiv:2405.03486）包含 10,146 张真实与 AI 生成图片、11 个不安全类别，并对 Q16、MultiHeaded、Stable Diffusion Safety Checker、LAION NSFW Detector、NudeNet 及三类 VLM 进行比较。论文明确指出：

- 成人和冲击性内容相对容易检测，仇恨、骚扰、自伤仍明显偏弱。
- 真实图片与 AI 生成图片存在分布偏移，传统 NSFW 分类器在 AI 图片上可能退化。
- 单一分类器覆盖面不足，多类别模型或组合方案更适合作为平台审核链路。
- 论文报告 PerspectiveVision 的 CLIP Linear Probing 在其测试集上总体 F1 为 0.859，LLaVA LoRA 版本总体 F1 为 0.844；这些是论文协议内结果，不能直接写成本站结果。

来源：[UnsafeBench 论文](https://arxiv.org/abs/2405.03486)；[官方仓库](https://github.com/YitingQu/UnsafeBench)

## 候选模型与用途

| 候选 | 适合任务 | 优点 | 限制 | 平台建议 |
|---|---|---|---|---|
| NudeNet | 裸露区域与成人内容召回 | 轻量、本地运行、可给区域框 | 类别很窄；对 AI 艺术图可能退化 | P0 shadow 召回器 |
| LAION CLIP NSFW Detector | 成人/NSFW 二分类 | CLIP 骨干，易输出连续分数 | 不能覆盖政治、营销等宽类别 | P0 与 MLLM 并行 |
| MultiHeaded | 成人、暴力、冲击、仇恨、政治 | 针对 AI 生成图训练，五头输出清晰 | 原始训练集仅约 800 张，仍需外部验证 | P1 宽类别补充 |
| Q16 | 通用“不安全”基线 | 轻量、适合作为对照 | 只有粗粒度安全/不安全，无法解释具体政策类 | 只做 benchmark 基线 |
| PerspectiveVision | 11 类宽范围审核 | 面向真实与 AI 图片，类别覆盖完整 | 7B VLM 部署成本高；需核对权重与许可证 | P1 在 4090 上离线评测 |
| UnsafeBench CLIP Linear Probing | 11 个独立类别分数 | 与平台逐类别评分契合，推理较轻 | 需要合法取得训练/测试数据和分类头权重 | P1 首选工程方向 |

## 4090 测试机实测

核查时间：2026-08-09。通过 SSH 配置别名 `4090x3` 连接测试机 `j4532-workstation`。

- GPU：3 张 NVIDIA GeForce RTX 4090，每张 24,564 MiB。
- 核查时 GPU0 空闲约 10,640 MiB；GPU1、GPU2 空闲不足 2 GiB，不适合立即启动 7B 模型。
- `hallo` 环境已有 PyTorch、Transformers 和 ONNX Runtime，可承载 NudeNet、CLIP NSFW Detector 或量化后的专用模型。
- 测试机没有发现 NudeNet、ShieldGemma、UnsafeBench 或 NSFW 模型缓存。
- 测试机当前不能访问 Hugging Face，不能直接在线下载权重；应在有网络的机器核对许可证和 SHA-256 后，通过受控方式传输模型制品。

因此，当前能够完成接口、评测器和运行环境准备，但在模型权重合法取得前不能伪造“已部署专用检测器”结论。

## 统一评测协议

每个类别独立报告：样本数、正负样本数、阈值、TP/TN/FP/FN、Precision、Recall、F1、ROC-AUC、PR-AUC、Brier、ECE 和 95% 置信区间。还必须增加：

- 分类分数覆盖率：模型是否对每个要求的类别都返回分数。
- 弃权率：模型拒答、解析失败或没有给出该类别分数的比例。
- 来源分层：真实图片和 AI 生成图片分别统计。
- 运营结论：协议内可用、能力受限、不可自动放行、证据待补。

Accuracy 不能作为首要指标。成人内容现有测试的 80% Accuracy 来自 60 个负样本全部判对，但 15 个正例全部漏报；其 Recall 和 F1 均为 0，运营结论只能是“不可自动放行”。
