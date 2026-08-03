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

报告只保留样本编号、标签、分类、分数、耗时和影子结果，不复制提示词或模型输出。`evaluations/results/` 已加入 Git 忽略。
