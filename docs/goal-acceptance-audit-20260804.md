# 总目标验收审计（2026-08-04）

以飞书总文档 `Z1OndNtyzoTk6WxyjjccOX0hnXc` revision 259 为唯一基线。本文件只记录当前可由代码、测试、生产响应或人工记录证明的状态。

| 目标域 | 当前状态 | 可核验证据 | 剩余动作 |
|---|---|---|---|
| 图片与人脸审核 | 已完成工程验收 | Deepfake/MLLM/RAG/人脸质量证据、上传硬化 12/12、后端全量测试 | 继续积累公开或授权真实样本；不引入身份识别/embedding |
| 实时大模型安全护栏 | 已完成工程验收 | 真实模型探针、输入/输出护栏、Qwen3Guard/SingGuard、P4-4 有界重试与 readiness | 按真实危险输出继续扩充评测集 |
| 红线知识库与主动扫描 | 已完成工程验收 | 规则/RAG/来源分类与 garak 主动扫描链路 | 维护比赛红线样本；garak 不进入实时请求路径 |
| 日志、审计、取证、开放 API | 已完成工程验收 | SQLite WAL、SHA-256 链、CSV、AES-GCM 证据库、租户/API Key/限流/配额 | 保持轮换、备份、最小权限；危险原文只留加密证据库 |
| 三层驾驶舱与现场自检 | 已完成工程验收 | 标准工作台/数据总览/大屏、readiness 13/13、HTTPS health | 当前版本官方应用内浏览器截图待运行资产恢复 |
| C2PA / Content Credentials | 已完成本轮工程验收 | `c2pa-python==0.37.2`；生产 valid fixture=`confirmed_source`；解析异常=`inconclusive`；无 manifest=`not_found`；93/93 测试 | 继续补充经过授权的生产发行者样本；不把 fixture 或 valid 当作 AI 生成结论 |
| 人工试标 P2-3.6 | 工程完成，真人验收未完成 | 200 条样本池、领取/证据查看/首次标签三步审计和只读 verifier | 真实审核员完成首批 20 条，再累计 200 条；当前 0/20、0/200，开发不得代填 |
| 昇腾 910 国产化 | 部分完成 | 16 卡健康、CANN、物理卡 2/3/4/5 四卡矩阵/MLP 微基准 | 根盘治理、卡号与隔离目录确认后再做护栏模型真实推理；不抢占现有任务 |

## C2PA 生产证据摘要

- 生产提交：`5ebe626`。
- 正式接口：`POST https://aigc.49.51.248.227.sslip.io/api/detect/provenance`。
- 有效公开夹具：`docs/evidence/c2pa-fixtures/c2pa-rs-update-manifest.jpg`，HTTP 200，`manifest_count=2`，`validation_state=valid`，`raw_image_retained=false`。
- 解析异常公开夹具：`docs/evidence/c2pa-fixtures/c2pa-rs-ocsp.jpg`，HTTP 200，`overall_state=inconclusive`，`error=manifest_parse_failed`。
- 无来源负样本：合成 PNG / `c2pa-rs-sample1.png`，`not_found`；不能推出“不是 AI”。

## 不可回退边界

原始提示词和模型危险输出继续完整保存在 AES-GCM 加密证据库；普通响应、日志、驾驶舱、CSV 和飞书只保留哈希、类别、状态、延迟和统计。人工标签必须由真实审核员本人提交，浏览器截图不得用绕过官方应用内浏览器限制的方式补造。
