# AI 安全审核系统本地模块

## 入口

```powershell
python security_audit_system/main.py "待审核文本"
```

批量逐行审核：

```powershell
python security_audit_system/main.py --file input.txt
```

## 输出

```json
{
  "decision": "pass",
  "confidence": 0.91,
  "alert": false,
  "latency_ms": 54.3,
  "risk_type": "safe",
  "route": "local",
  "votes": []
}
```

- `decision`：主结果，只输出 `pass` 或 `fail`。
- `confidence`：融合置信度。
- `alert`：低置信或边界样本复核标记，不改变主结果。
- `votes`：本地专家投票记录，包括规则、TF-IDF、朴素贝叶斯、XGBoost 等。
- 默认不输出相似样本 `evidence`，避免额外检索耗时；如需解释，可查看 `votes`。

## 配置

配置文件：`security_audit_system/config.json`

```json
{
  "model_path": "models/hybrid_safety_model_xgboost_color.json",
  "alert_confidence_threshold": 0.60,
  "enable_alert": true,
  "include_votes": true
}
```

本模块不调用 DeepSeek，也不调用云端 embedding。当前只保留本地规则、关键词、TF-IDF、朴素贝叶斯、XGBoost 和专家融合结果。

## 当前评估结果

最新本地低延迟评估：

| 范围 | 严格准确率 | 运营准确率 | FN | FP | alert |
|---|---:|---:|---:|---:|---:|
| 全量 3663 条 | 98.77% | 99.15% | 12 | 19 | 66 |
| 第一张表 2221 条 | 98.74% | 99.01% | 4 | 18 | 58 |

平均延迟约 54.30ms/条。第一张表正确率超过 95%。
