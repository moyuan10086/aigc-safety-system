"""
Deepfake 检测服务 — 复用 deepfake-detection 项目模块
"""
import hashlib
import sys
from pathlib import Path

DFDET_ROOT = Path(__file__).parents[2] / "deepfake-detection"
sys.path.insert(0, str(DFDET_ROOT))

import torch  # noqa: E402
from PIL import Image  # noqa: E402
from huggingface_hub import hf_hub_download  # noqa: E402
from src.config import Config  # noqa: E402
from src.model.dfdet import DeepfakeDetectionModel  # noqa: E402

_model = None
_preprocess = None
_device = "cuda" if torch.cuda.is_available() else "cpu"


def _load():
    global _model, _preprocess
    if _model is not None:
        return

    weights_dir = DFDET_ROOT / "weights"
    ckpt_path = weights_dir / "model.ckpt"
    if not ckpt_path.exists():
        ckpt_path = Path(hf_hub_download(
            repo_id="yermandy/deepfake-detection",
            filename="model.ckpt",
            local_dir=str(weights_dir),
        ))

    ckpt = torch.load(str(ckpt_path), map_location="cpu")
    model = DeepfakeDetectionModel(Config(**ckpt["hyper_parameters"]))
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    _preprocess = model.get_preprocessing()

    # CPU: force float32 (bf16 not supported for CPU convolutions)
    if not torch.cuda.is_available():
        model = model.float()
    model = model.to(_device)

    _model = model

_cache: dict = {}


def _md5(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def detect(image_path: str) -> dict:
    """Returns: {"score": float, "label": "fake"|"real", "confidence": float}"""
    key = _md5(image_path)
    if key in _cache:
        return _cache[key]
    _load()
    img = Image.open(image_path).convert("RGB")
    tensor = _preprocess(img).unsqueeze(0).to(_device)
    if not torch.cuda.is_available():
        tensor = tensor.float()

    with torch.no_grad():
        output = _model(tensor)
        probs = output.logits_labels.softmax(dim=1).float().cpu().numpy()[0]

    p_real, p_fake = float(probs[0]), float(probs[1])
    result = {
        "score": round(p_fake, 4),
        "label": "fake" if p_fake >= 0.5 else "real",
        "confidence": round(max(p_real, p_fake), 4),
    }
    _cache[key] = result
    return result
