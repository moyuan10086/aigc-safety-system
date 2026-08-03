"""
RAG 内容安全审核服务 — ChromaDB + Sensitive-lexicon
"""
import sys
from pathlib import Path
import chromadb
from sentence_transformers import SentenceTransformer
from config import CHROMA_PATH, LEXICON_PATH

# SensitiveLexiconLoader 已复制到 backend/
BACKEND_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BACKEND_DIR))

_client = None
_collection = None
_embedder = None
_keywords: list[str] = []
_keyword_categories: dict[str, str] = {}


def _init():
    global _client, _collection, _embedder, _keywords, _keyword_categories
    if _client is not None:
        return

    _client = chromadb.PersistentClient(path=CHROMA_PATH)

    # 检测并修复损坏的 collection
    try:
        _collection = _client.get_or_create_collection("safety_rules")
        # 测试 collection 是否可用
        if _collection.count() > 0:
            _collection.query(
                query_embeddings=[[0.0] * 384],
                n_results=1,
            )
    except Exception:
        # 删除损坏的 collection 并重建
        try:
            _client.delete_collection("safety_rules")
        except Exception:
            pass
        _collection = _client.create_collection("safety_rules")
    _embedder = SentenceTransformer(
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        cache_folder=str(Path(__file__).parents[1] / "weights" / "sentence_transformers"),
        local_files_only=False,
    )

    # 用 SensitiveLexiconLoader 加载词库
    try:
        from sensitive_lexicon_loader import SensitiveLexiconLoader
        loader = SensitiveLexiconLoader(lexicon_dir=LEXICON_PATH)
        all_kw = loader.load_all()
        for category, words in all_kw.items():
            _keywords.extend(words)
            for word in words:
                _keyword_categories.setdefault(word, category)
        print(f"[RAG] 加载敏感词 {len(_keywords)} 条")
    except Exception as e:
        print(f"[RAG] SensitiveLexiconLoader 不可用，回退到直接读取: {e}")
        lex_path = Path(LEXICON_PATH)
        if lex_path.exists():
            for f in lex_path.glob("*.txt"):
                try:
                    with open(f, encoding="utf-8") as fp:
                        _keywords.extend([
                            line.strip()
                            for line in fp
                            if line.strip() and not line.startswith("#")
                        ])
                except Exception:
                    pass

    if _collection.count() == 0:
        _init_kb()


def _init_kb():
    rules = [
        "禁止色情、淫秽、暴力、血腥内容",
        "禁止政治敏感话题和违法犯罪内容",
        "禁止儿童色情和未成年人不当内容",
        "禁止自残、自杀相关内容",
        "禁止仇恨言论、歧视和骚扰",
    ]
    embeddings = _embedder.encode(rules).tolist()
    _collection.add(
        ids=[f"rule_{i}" for i in range(len(rules))],
        embeddings=embeddings,
        documents=rules,
    )


def check_content(text: str) -> dict:
    """Run keyword and semantic redline checks with traceable evidence."""
    global _collection
    _init()

    matched = [kw for kw in _keywords if kw and kw.lower() in text.lower()][:10]
    matches = [
        {
            "term": keyword,
            "category": _keyword_categories.get(keyword, "other"),
            "source": "Sensitive-lexicon",
            "ability": "keyword_match",
        }
        for keyword in matched
    ]

    violated = []
    semantic_matches = []
    try:
        query_emb = _embedder.encode([text]).tolist()
        results = _collection.query(query_embeddings=query_emb, n_results=3)
        if results["distances"][0][0] < 0.5:
            violated = results["documents"][0]
            semantic_matches = [
                {
                    "rule": rule,
                    "distance": round(float(distance), 4),
                    "score": round(max(0.0, 1.0 - float(distance)), 4),
                    "source": "safety_rules",
                    "ability": "semantic_match",
                }
                for rule, distance in zip(results["documents"][0], results["distances"][0])
                if distance is not None and float(distance) < 0.5
            ]
    except Exception:
        _collection.delete(ids=_collection.get()["ids"] or ["_"])
        _init_kb()

    risk = "high" if matched else ("medium" if violated else "low")
    categories = sorted({item["category"] for item in matches})
    safe = not (matched or violated)
    return {
        "safe": safe,
        "matched_keywords": matched,
        "violated_rules": violated,
        "risk_level": risk,
        "decision": "safe" if safe else ("unsafe" if matched else "borderline"),
        "risk_code": "SAFE_000" if safe else ("REDLINE_KEYWORD_001" if matched else "REDLINE_SEMANTIC_001"),
        "categories": categories,
        "matches": matches,
        "semantic_matches": semantic_matches,
        "action": "allow" if safe else ("block" if matched else "manual_review"),
        "source": "Sensitive-lexicon + ChromaDB",
    }
