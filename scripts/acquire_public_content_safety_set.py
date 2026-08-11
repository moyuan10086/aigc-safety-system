"""Acquire a small, licensed, label-backed image-safety evaluation set.

Raw images stay in a caller-provided cache outside Git. The generated manifest
records pinned Hugging Face revisions, source paths, labels, and file hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DATASETS = {
    "weapon": {
        "repo": "Simuletic/CCTV_Weapon_Detection_Rifles_vs_Umbrellas",
        "license": "cc-by-nc-4.0",
    },
    "violence": {
        "repo": "farazv2/violence-detection-violence-class",
        "license": "mit",
    },
    "adult": {
        "repo": "Anik121/NSFW_Image",
        "license": "mit",
    },
}


def _json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def _bytes(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=90) as response:
        return response.read()


def _dataset_info(repo: str) -> dict[str, Any]:
    return _json(f"https://huggingface.co/api/datasets/{repo}")


def _tree(repo: str, revision: str) -> list[dict[str, Any]]:
    quoted_revision = urllib.parse.quote(revision, safe="")
    return _json(
        f"https://huggingface.co/api/datasets/{repo}/tree/{quoted_revision}"
        "?recursive=true&expand=false"
    )


def _resolve_url(repo: str, revision: str, path: str) -> str:
    return (
        f"https://huggingface.co/datasets/{repo}/resolve/"
        f"{urllib.parse.quote(revision, safe='')}/"
        f"{urllib.parse.quote(path, safe='/')}?download=true"
    )


def _write_sample(cache: Path, repo: str, revision: str, source_path: str) -> tuple[Path, str]:
    data = _bytes(_resolve_url(repo, revision, source_path))
    digest = hashlib.sha256(data).hexdigest()
    suffix = Path(source_path).suffix.lower() or ".bin"
    target = cache / "images" / f"{digest}{suffix}"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(data)
    return target, digest


def _weapon_paths(repo: str, revision: str, tree: list[dict[str, Any]], count: int) -> list[tuple[str, bool]]:
    labels = sorted(
        item["path"] for item in tree
        if item.get("type") == "file" and "/labels/" in item.get("path", "") and item["path"].endswith(".txt")
    )
    positives: list[str] = []
    negatives: list[str] = []
    for label_path in labels:
        text = _bytes(_resolve_url(repo, revision, label_path)).decode("utf-8", errors="replace")
        classes = {line.split()[0] for line in text.splitlines() if line.strip()}
        image_path = label_path.replace("/labels/", "/images/").removesuffix(".txt") + ".JPG"
        if "1" in classes:
            positives.append(image_path)
        elif "2" in classes:
            negatives.append(image_path)
    if len(positives) < count or len(negatives) < count:
        raise RuntimeError(f"weapon dataset has only {len(positives)} positives and {len(negatives)} negatives")
    return [(path, True) for path in positives[:count]] + [(path, False) for path in negatives[:count]]


def _violence_paths(tree: list[dict[str, Any]], count: int) -> list[tuple[str, bool]]:
    images = sorted(
        item["path"] for item in tree
        if item.get("type") == "file" and "/images/" in item.get("path", "")
        and Path(item["path"]).suffix.lower() in {".jpg", ".jpeg", ".png"}
    )
    positives = [path for path in images if "/Violence_" in path]
    negatives = [path for path in images if "/NonViolence_" in path]
    if len(positives) < count or len(negatives) < count:
        raise RuntimeError(f"violence dataset has only {len(positives)} positives and {len(negatives)} negatives")
    return [(path, True) for path in positives[:count]] + [(path, False) for path in negatives[:count]]


def _adult_paths(tree: list[dict[str, Any]], count: int) -> list[str]:
    images = sorted(
        item["path"] for item in tree
        if item.get("type") == "file" and "/gen_outputs/" in item.get("path", "")
        and Path(item["path"]).suffix.lower() in {".jpg", ".jpeg", ".png"}
    )
    if len(images) < count:
        raise RuntimeError(f"adult dataset has only {len(images)} images")
    return images[:count]


def acquire(cache: Path, *, per_class: int) -> dict[str, Any]:
    cache.mkdir(parents=True, exist_ok=True)
    resolved: dict[str, dict[str, Any]] = {}
    for key, config in DATASETS.items():
        info = _dataset_info(config["repo"])
        revision = str(info["sha"])
        resolved[key] = {**config, "revision": revision, "tree": _tree(config["repo"], revision)}

    selected: list[tuple[str, str, bool, str]] = []
    weapon = resolved["weapon"]
    for source_path, positive in _weapon_paths(weapon["repo"], weapon["revision"], weapon["tree"], per_class):
        selected.append(("weapon", source_path, positive, "weapon_display" if positive else ""))
    violence = resolved["violence"]
    for source_path, positive in _violence_paths(violence["tree"], per_class):
        selected.append(("violence", source_path, positive, "violence" if positive else ""))
    adult = resolved["adult"]
    for source_path in _adult_paths(adult["tree"], per_class):
        selected.append(("adult", source_path, True, "adult_content"))

    rows: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {}
    for index, (source_key, source_path, _positive, label) in enumerate(selected, 1):
        dataset = resolved[source_key]
        local_path, digest = _write_sample(cache, dataset["repo"], dataset["revision"], source_path)
        source_counts[source_key] = source_counts.get(source_key, 0) + 1
        rows.append({
            "sample_id": f"public-{index:03d}",
            "image_path": str(local_path.resolve()),
            "reference_labels": [label] if label else [],
            "dataset_id": "public_content_safety_v1",
            "split": "test",
            "source": f"hf://datasets/{dataset['repo']}@{dataset['revision']}/{source_path}",
            "source_sha256": digest,
        })

    manifest = {
        "schema": "aigc.public-content-safety-manifest.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_count": len(rows),
        "per_class": per_class,
        "datasets": {
            key: {
                "repo": value["repo"],
                "revision": value["revision"],
                "license": value["license"],
                "selected_count": source_counts.get(key, 0),
            }
            for key, value in resolved.items()
        },
        "label_protocol": {
            "weapon_display": "YOLO class 1 rifle is positive; umbrella-only is negative",
            "violence": "RLVS filename ground truth: Violence positive, NonViolence negative",
            "adult_content": "Anik121 generated NSFW images are positive; all other selected benchmark images are explicit negatives",
        },
        "limitations": [
            "The adult-content task uses cross-source negatives and must not be presented as a universal real-world estimate.",
            "Political-sensitive and marketing-violation tasks are excluded because no license-verified dataset with matching business labels was found.",
            "Raw images remain in the external evaluation cache and are not committed or deployed as public assets.",
        ],
        "samples": rows,
    }
    manifest_path = cache / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"manifest": str(manifest_path), "sample_count": len(rows), "datasets": manifest["datasets"]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Acquire licensed public content-safety evaluation images")
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--per-class", type=int, default=15)
    args = parser.parse_args()
    print(json.dumps(acquire(args.cache, per_class=args.per_class), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
