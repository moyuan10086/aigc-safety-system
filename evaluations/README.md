# 护栏评测

## 12 条 CI 冒烟回归

`promptfooconfig.yaml` 用于每次提交的快速输入/输出侧回归，不读取生产密钥，也不写审计证据。

## P2-2 中文校准集

`calibration_cases.py` 生成至少 100 条确定性合成样本，覆盖安全科普、越狱、提示词注入、网络攻击滥用、武器、自伤、色情、未成年人、违法、仇恨、隐私和 Agent 危险操作。

离线规则基线：

```powershell
uv run python run_calibration.py --offline --output results/calibration-offline.json
```

正式环境真实专家链路：

```powershell
uv run python run_calibration.py --output results/calibration-production.json
```

## P2-3 独立改写盲测

`blind_cases.py` 提供 60 条不直接复用 P2-2 正则模板的语义改写样本。它用于揭示规则路径和语义专家的真实覆盖差异，合成标签不能冒充人工确认标签。

离线规则基线：

```powershell
uv run python run_calibration.py --offline --case-set blind --workers 2 --output results/blind-offline.json
```

正式环境限并发专家链：

```powershell
uv run python run_calibration.py --case-set blind --workers 2 --sla-seconds 30 --output results/blind-production.json
```

运行摘要包含吞吐、平均/P95 延迟、SLA 超限数、异常数、降级率和各组件状态分布。`--workers` 最大限制为 8，正式服务器默认使用 2，避免评测流量压垮本地模型服务。

在线护栏默认通过 `GUARDRAIL_PARALLEL_EXPERTS=true` 并行调用彼此独立的 RAG、Qwen3Guard、SingGuard 和可选 MLLM；融合阈值、证据顺序和 XGBoost 影子边界不变。可设置 `GUARDRAIL_PARALLEL_EXPERTS=false` 立即回退到串行路径，`GUARDRAIL_EXPERT_MAX_WORKERS` 的硬上限为 4。

报告的 `run.component_latency_ms` 记录规则、各专家、专家阶段、XGBoost 与总链路的平均/P95 耗时，用于定位性能瓶颈。它只包含组件名与时长，不包含原始输入或模型输出。

报告只保留样本编号、标签、分类、分数、耗时和影子结果，不复制提示词或模型输出。`evaluations/results/` 已加入 Git 忽略。
