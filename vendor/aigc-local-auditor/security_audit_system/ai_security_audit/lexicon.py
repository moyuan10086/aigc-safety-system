from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_LEXICON_DIR = Path(r"D:\文件\大学\毕设\数字人前端\backend\Sensitive-lexicon\Vocabulary")
LEXICON_ENV = "AI_AUDIT_LEXICON_DIR"
STOP_TERMS = {
    "制度",
    "政治",
    "国家",
    "我国",
    "中国",
    "人民",
    "社会",
    "系统",
    "问题",
    "内容",
    "安全",
}


@dataclass(frozen=True)
class LexiconHit:
    term: str
    category: str
    start: int
    end: int


class SensitiveLexicon:
    """Local sensitive word matcher backed by plain-text vocabulary files."""

    def __init__(self, root: str | Path | None = None, *, max_term_length: int = 64) -> None:
        self.root = Path(root or os.getenv(LEXICON_ENV) or DEFAULT_LEXICON_DIR)
        self.max_term_length = max_term_length
        self._index: dict[str, list[tuple[str, str]]] = {}
        self.term_count = 0
        if self.root.exists():
            self._load()

    @property
    def available(self) -> bool:
        return bool(self._index)

    def find(self, text: str, *, max_hits: int = 8) -> list[LexiconHit]:
        normalized = text.lower()
        hits: list[LexiconHit] = []
        for start, char in enumerate(normalized):
            candidates = self._index.get(char)
            if not candidates:
                continue
            window = normalized[start : start + self.max_term_length]
            for term, category in candidates:
                if window.startswith(term):
                    hits.append(LexiconHit(term=term, category=category, start=start, end=start + len(term)))
                    if len(hits) >= max_hits:
                        return hits
        return hits

    def _load(self) -> None:
        for path in sorted(self.root.glob("*.txt")):
            category = path.stem
            for term in self._read_terms(path):
                normalized = term.strip().lower()
                if not self._is_usable_term(normalized, category):
                    continue
                self._index.setdefault(normalized[0], []).append((normalized, category))
                self.term_count += 1
        for terms in self._index.values():
            terms.sort(key=lambda item: len(item[0]), reverse=True)

    def _read_terms(self, path: Path) -> list[str]:
        for encoding in ("utf-8", "utf-8-sig", "gb18030"):
            try:
                return path.read_text(encoding=encoding).splitlines()
            except UnicodeDecodeError:
                continue
        return path.read_text(errors="ignore").splitlines()

    def _is_usable_term(self, term: str, category: str) -> bool:
        if not term or term.startswith("#"):
            return False
        if len(term) > self.max_term_length:
            return False
        if term in STOP_TERMS:
            return False
        high_value_category = any(keyword in category for keyword in ("暴恐", "涉枪", "涉爆", "色情", "非法网址"))
        if not high_value_category and len(term) <= 2 and all("\u4e00" <= char <= "\u9fff" for char in term):
            return False
        if len(term) == 1 and not ("\u4e00" <= term <= "\u9fff"):
            return False
        return True
