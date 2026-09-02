# 模型清单与获取方式

本文档记录 AIGC Safety System 的模型依赖、来源和部署边界。模型权重不提交到代码仓库，公开可分发的运行时资产统一托管在：

- [Hugging Face：moyuan10086/aigc-safety-models](https://huggingface.co/moyuan10086/aigc-safety-models)
- [ModelScope：moyuan10086/aigc-safety-models](https://modelscope.cn/models/moyuan10086/aigc-safety-models)

## 可公开获取的本地模型

| 能力 | 模型/文件 | 用途 | 代码配置 | 来源与说明 |
| --- | --- | --- | --- | --- |
| Deepfake 检测 | `deepfake/model-epoch6.ckpt` | 逐脸真实性检测 | `DEEPFAKE_MODEL_PATH` | 本项目基于 DF40 + DeepFakeFace 的第 6 轮平台微调 checkpoint；SHA-256 为 `fd0b967e9ab6a19aa0127c5c2301b3883ff8013b1a5d7af282e29737132c1fb9` |
| 人脸检测 | `deepfake/face_detection_yunet_2023mar.onnx` | YuNet 人脸框和五点关键点 | `DEEPFAKE_FACE_MODEL_PATH` | OpenCV Zoo 模型，使用时保留上游许可证和署名 |
| RAG 语义检索 | `embedding/paraphrase-multilingual-MiniLM-L12-v2/` | 中文/多语言政策文本向量化 | `backend/services/kb_service.py` 的本地缓存目录 | Sentence-Transformers 公开模型，遵循其模型卡和许可证 |
| Shadow 审核 | `shadow/hybrid_safety_model_xgboost_color.json` | 旁路观察模型分歧和规则盲区 | `GUARDRAIL_XGBOOST_SHADOW_MODEL_PATH` | 本地混合安全模型；只参与观察和评估，不覆盖生产护栏结论 |

模型仓库中的目录结构为：

```text
aigc-safety-models/
├── deepfake/
│   ├── model-epoch6.ckpt
│   └── face_detection_yunet_2023mar.onnx
├── embedding/
│   └── paraphrase-multilingual-MiniLM-L12-v2/
├── shadow/
│   └── hybrid_safety_model_xgboost_color.json
└── README.md
```

## 外部服务或运行时下载模型

下列模型在系统中使用，但其权重不随公开模型仓库分发：

| 模型 | 系统用途 | 当前接入方式 | 公开仓库状态 |
| --- | --- | --- | --- |
| `qwen3guard-gen-0.6b` | 通用文本内容安全分类 | `GUARDRAIL_QWEN_BASE_URL` 指向 OpenAI 兼容服务 | 仅调用服务，不复制服务端权重 |
| `singguard-nsfa-0.8b` | Agent、提示词注入、数据窃取和工具滥用风险识别 | `GUARDRAIL_SINGGUARD_BASE_URL` 指向 OpenAI 兼容服务 | 仅调用服务，不复制服务端权重 |
| MLLM / 文本生成模型 | 真实性解释、复杂语义复核和受保护模型生成 | `MLLM_BASE_URL`、`MLLM_MODEL`、`CHAT_MODEL_BASE_URL`、`CHAT_MODEL_NAME` | 由部署方配置的网关提供 |
| PaddleOCR 模型 | 图片/PDF 文字识别 | PaddleOCR 运行时按其安装流程下载 | 遵循 PaddleOCR 和模型文件的许可证 |
| NudeNet `320n.onnx`（可选） | 视觉内容安全增强专家 | `NUDENET_MODEL_PATH` | 仅在获授权并配置时启用 |

未配置上述外部模型时，系统仍可运行规则、RAG、审计和基础审核流程；相关模块返回 `unavailable`、`degraded` 或 `inconclusive`，不会静默当作安全。

## 部署建议

1. 从 Hugging Face 或 ModelScope 固定版本下载公开模型资产，并在部署机保存到独立模型目录。
2. 计算文件 SHA-256，与模型仓库 README 和发布记录核对后再启用。
3. 通过 `.env` 设置本地路径和服务地址，避免把权重、Token、上传文件和证据库提交到 Git。
4. 使用第三方模型前核对其许可证、数据集条款和再分发限制；模型仓库的公开状态不代表所有组成模型都由本项目拥有版权。
