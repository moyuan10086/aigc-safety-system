# 官方 UnsafeBench 复测记录（2026-08-12）

## 数据与协议

- 数据集：[yiting/UnsafeBench](https://huggingface.co/datasets/yiting/UnsafeBench)
- 固定 revision：`9f4560ae90059237eb5eafc6bd8108c78639d180`
- Train：8,109 张；Test：2,037 张；合计 10,146 张
- Test 标签：Safe 1,260，Unsafe 777
- Test 类别：Deception、Harassment、Hate、Illegal activity、Political、Public and personal health、Self-harm、Sexual、Shocking、Spam、Violence
- Test 来源：Laion5B 1,015；Lexica 1,022
- Test Parquet SHA-256：`c1fd60ac62277a45c568d670adb60824881a05f4e041148a08f2547278b8f59c`
- 原始图像仅保留在 4090 隔离评测目录，证据文件只保留样本哈希、标签、模型结果与时延。

## 官方 Test 结果

| 引擎 | 样本 | Accuracy | Precision | Recall | F1 | 平均时延 | P95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| MultiHeaded + Q16 高速初筛 | 2,037 | 71.97% | 66.35% | 53.80% | 59.42% | 35.1 ms | 81.4 ms |
| PerspectiveVision-LLaVA 二次审核 | 2,037 | 87.14% | 78.08% | 92.15% | 84.53% | 809.9 ms | 1,004.8 ms |

混淆矩阵：MultiHeaded+Q16 为 TP 418 / TN 1048 / FP 212 / FN 359；PerspectiveVision 为 TP 716 / TN 1059 / FP 201 / FN 61。

## Train 覆盖诊断

MultiHeaded+Q16 对 Train 8,109 张全部完成推理：Accuracy 69.61%、Precision 65.54%、Recall 52.03%、F1 58.01%，平均 118.7 ms。该结果只用于覆盖与阈值校准诊断，不能替代 Test 指标。

## 展示口径

平台正式采用级联叙事：MultiHeaded+Q16 的优势是约 35 ms 的高速初筛；PerspectiveVision 的优势是官方 Test Recall 92.15%、F1 84.53%，作为高召回二次审核。两者不合并为一个虚假的总准确率，也不把五头 MultiHeaded 解释成 11 类完整分类器。

## 边界

当前 MultiHeaded+Q16 仅包含 sexual、violent、disturbing、hateful、political 五个专家头，官方 UnsafeBench 的其余类别仍由 PerspectiveVision/MLLM/规则链路覆盖。阈值未在 Test 上反向挑选；后续可在 Train 上做固定阈值校准后重新锁定 Test 复测。
