# SingGuard 复测记录（2026-08-12）

## 已完成冻结盲测

- 数据：平台 `blind_cases.py` 的 60 条冻结语义改写样本
- 标签性质：合成测试期望，不是公开基准、人工生产标注或论文结果
- SingGuard-NSFA-0.8B 生成式服务
- Accuracy 91.67%，Precision 100%，Recall 83.33%，F1 90.91%
- TP 25 / TN 30 / FP 0 / FN 5
- 平均时延 5,305 ms，P50 5,234 ms，P95 6,928 ms

该结果可用于回归与展示“高精度、零误报辅助专家”，不能外推为公开数据集精度。

## 官方 NSFA 数据集

已通过临时代理下载 Apache-2.0 数据集：[inclusionAI/NSFA_Benchmarks](https://huggingface.co/datasets/inclusionAI/NSFA_Benchmarks)，revision `54b390c5b9c26ec40ce7f660e278d909f4dad8dc`。

- Cross-source Query：3,435 条，来自 AgentDojo、InjecAgent、AgentHarm、AgentDyn、ATBench
- Query Multilingual：63,431 条
- Response Multilingual：29,972 条
- 覆盖 133 种语言、7 个一级风险域

官方实时模式需要取冻结主干最后 token embedding，再运行 `nsfa_heads/` 下的 MLP 分类头。首次批量运行错误调用完整语言模型头，为每个 token 计算约 15 万词表 logits，因额外申请约 18.8 GiB 显存中止。修正为仅调用 `model.model(...)` 主干 hidden-state 后，正式评测已完成。

## 官方 Cross-source Query 实测

- 样本：3,435 条，正类 2,315，负类 1,120
- 模型：SingGuard-NSFA-0.8B 官方实时分类头模式
- Accuracy：81.98%
- Precision：79.92%
- Recall：97.84%
- F1：87.98%
- 混淆矩阵：TP 2,265 / TN 551 / FP 569 / FN 50
- 单条平均时延：28.78 ms，P50 26.89 ms，P95 40.05 ms
- 总耗时：98.89 秒
- 完成率：3,435 / 3,435

该结果来自公开跨来源、多语言基准，可作为比赛展示的正式证据。模型优势是极高风险召回与实时分类速度；Precision 低于 80% 表明存在一定误报，因此定位为实时高召回护栏和辅助阻断，复核链路仍保留。原始机器可读证据为 `singguard-nsfa-crosssource3435-20260812.json`。
