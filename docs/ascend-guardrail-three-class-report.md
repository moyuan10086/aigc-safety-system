# 昇腾 910C 三类安全分类真实验证

本次在不停止、不抢占现有任务的前提下，复用 `100.121.203.95` 上已有 vLLM-Ascend 服务，对安全、边界、危险三个中文样本做结构化分类。模型为 `qwen3-235b-a22b-thinking-2507-w8a8-64k-target`，不是 Qwen3Guard。

三例实际返回分别为 `safe`、`borderline`、`unsafe`，与预期一致；延迟分别为 3917、1921、3009 ms。请求使用 OpenAI 兼容接口的 `response_format=json_object`。未启用该模式时，thinking 模型会输出解释文本，平台必须按 `inconclusive` 降级，不能直接当成护栏结论。

资源检查显示：物理卡 8–15 已被现有 vLLM 占用，物理卡 0 有长期任务；1–7 虽然 HBM 较低，但属于长期 `sandbox-42` 多进程容器，也不视为空闲。本次没有停止进程、抢占卡、下载权重或清理文件。共享模型盘未发现 Qwen3Guard、LlamaGuard、WildGuard、SingGuard 等专用护栏权重。

针对通用模型可能返回平台词表以外类别的问题，平台已补充失败安全逻辑：当结构化 verdict 为 `unsafe` 或 `borderline`、但类别/分数被白名单过滤为空时，保留 `policy_violation` 兜底风险，不让正确的危险 verdict 被静默丢失。

结论只证明国产昇腾真实三类安全分类链路可行，不证明专用 Qwen3Guard 已部署，也不证明三例结果具备统计意义。专用模型仍需在兼容权重和明确卡位可用后，完成更大中文评测集的召回率、误报率、P95 延迟、吞吐与 HBM 测试。
