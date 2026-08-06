from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from .core import AISecurityAuditor

EmbeddingClient = Any


def dense_cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)

try:
    import numpy as np
except Exception:  # pragma: no cover - optional speedup
    np = None

try:
    from sklearn.ensemble import GradientBoostingClassifier
except Exception:  # pragma: no cover - optional dependency
    GradientBoostingClassifier = None


@dataclass(frozen=True)
class ModelVote:
    source: str
    decision: str
    confidence: float
    reason: str = ""
    risk_type: str = ""


@dataclass(frozen=True)
class HybridAuditResult:
    decision: str
    confidence: float
    votes: list[ModelVote]
    route: str = "local"
    risk_type: str = ""
    explanation: str = ""
    cloud_recommended: bool = False
    evidence: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "confidence": self.confidence,
            "route": self.route,
            "risk_type": self.risk_type,
            "explanation": self.explanation,
            "cloud_recommended": self.cloud_recommended,
            "evidence": self.evidence or {},
            "votes": [asdict(vote) for vote in self.votes],
        }


class CharNgramVectorizer:
    def __init__(self, ngram_range: tuple[int, int] = (2, 4), max_features: int = 12000) -> None:
        self.ngram_range = ngram_range
        self.max_features = max_features
        self.vocabulary: dict[str, int] = {}
        self.idf: dict[str, float] = {}

    def fit(self, texts: Iterable[str]) -> None:
        texts = list(texts)
        document_frequency: Counter[str] = Counter()
        term_frequency: Counter[str] = Counter()
        for text in texts:
            terms = self._ngrams(text)
            term_frequency.update(terms)
            document_frequency.update(set(terms))
        most_common = [term for term, _ in term_frequency.most_common(self.max_features)]
        self.vocabulary = {term: index for index, term in enumerate(most_common)}
        total_docs = max(1, len(texts))
        self.idf = {
            term: math.log((1 + total_docs) / (1 + document_frequency[term])) + 1.0
            for term in self.vocabulary
        }

    def transform(self, text: str) -> dict[str, float]:
        counts = Counter(term for term in self._ngrams(text) if term in self.vocabulary)
        if not counts:
            return {}
        total = sum(counts.values())
        vector = {term: (count / total) * self.idf.get(term, 1.0) for term, count in counts.items()}
        norm = math.sqrt(sum(value * value for value in vector.values()))
        if norm:
            vector = {term: value / norm for term, value in vector.items()}
        return vector

    def to_dict(self) -> dict[str, Any]:
        return {
            "ngram_range": list(self.ngram_range),
            "max_features": self.max_features,
            "vocabulary": self.vocabulary,
            "idf": self.idf,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CharNgramVectorizer":
        vectorizer = cls(tuple(data["ngram_range"]), int(data["max_features"]))
        vectorizer.vocabulary = {str(key): int(value) for key, value in data["vocabulary"].items()}
        vectorizer.idf = {str(key): float(value) for key, value in data["idf"].items()}
        return vectorizer

    def _ngrams(self, text: str) -> list[str]:
        normalized = normalize_text(text)
        chars = [char for char in normalized if not char.isspace()]
        terms: list[str] = []
        min_n, max_n = self.ngram_range
        for n in range(min_n, max_n + 1):
            terms.extend("".join(chars[index : index + n]) for index in range(0, max(0, len(chars) - n + 1)))
        terms.extend(re.findall(r"[A-Za-z0-9_]{2,}", normalized.lower()))
        return terms


class VectorSafetyIndex:
    def __init__(self, vectorizer: CharNgramVectorizer | None = None) -> None:
        self.vectorizer = vectorizer or CharNgramVectorizer()
        self.items: list[dict[str, Any]] = []

    def fit(self, examples: list[dict[str, str]]) -> None:
        self.vectorizer.fit(example["text"] for example in examples)
        self.items = []
        for index, example in enumerate(examples):
            self.items.append(
                {
                    "id": index,
                    "text": example["text"],
                    "label": example["label"],
                    "vector": self.vectorizer.transform(example["text"]),
                }
            )

    def vote(self, text: str, k: int = 7) -> ModelVote:
        top = self.top_matches(text, k=k)
        if not top:
            return ModelVote("vector", "alert", 0.0, "no vector match")
        label_scores: defaultdict[str, float] = defaultdict(float)
        for score, item in top:
            label_scores[str(item["label"])] += score
        decision, score = max(label_scores.items(), key=lambda item: item[1])
        total = sum(label_scores.values())
        confidence = score / total if total else 0.0
        reason = f"top_sim={top[0][0]:.3f}, k={len(top)}"
        return ModelVote("vector", decision, confidence, reason, "similar_case")

    def top_matches(self, text: str, k: int = 7) -> list[tuple[float, dict[str, Any]]]:
        query = self.vectorizer.transform(text)
        if not query or not self.items:
            return []
        scored: list[tuple[float, dict[str, Any]]] = []
        for item in self.items:
            score = cosine(query, item["vector"])
            if score > 0:
                scored.append((score, item))
        return sorted(scored, key=lambda item: item[0], reverse=True)[:k]

    def feature_stats(self, text: str, k: int = 7) -> list[float]:
        top = self.top_matches(text, k=k)
        if not top:
            return [0.0, 0.0, 0.0, 0.0]
        label_scores: defaultdict[str, float] = defaultdict(float)
        for score, item in top:
            label_scores[str(item["label"])] += score
        total = sum(label_scores.values())
        fail_ratio = label_scores["fail"] / total if total else 0.0
        pass_ratio = label_scores["pass"] / total if total else 0.0
        return [float(top[0][0]), fail_ratio, pass_ratio, abs(fail_ratio - pass_ratio)]

    def similar_examples(self, text: str, k: int = 3) -> list[dict[str, Any]]:
        return [
            {
                "score": round(score, 4),
                "label": item.get("label"),
                "text": str(item.get("text", ""))[:120],
            }
            for score, item in self.top_matches(text, k=k)
        ]

    def to_dict(self) -> dict[str, Any]:
        return {"vectorizer": self.vectorizer.to_dict(), "items": self.items}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VectorSafetyIndex":
        index = cls(CharNgramVectorizer.from_dict(data["vectorizer"]))
        index.items = data["items"]
        return index


class RemoteEmbeddingSafetyIndex:
    def __init__(
        self,
        *,
        embedding_client: EmbeddingClient | None = None,
        provider: str = "bigmodel",
        model: str = "embedding-3",
        vote_mode: str = "assist",
    ) -> None:
        self.embedding_client = embedding_client
        self.provider = provider
        self.model = model
        self.vote_mode = vote_mode
        self.items: list[dict[str, Any]] = []
        self._matrix: Any = None
        self._labels: list[str] = []

    def fit(self, examples: list[dict[str, str]]) -> None:
        if not self.embedding_client:
            raise ValueError("RemoteEmbeddingSafetyIndex.fit requires embedding_client")
        texts = [example["text"] for example in examples]
        vectors = self.embedding_client.embed_texts(texts)
        self.items = []
        for index, (example, vector) in enumerate(zip(examples, vectors)):
            self.items.append(
                {
                    "id": index,
                    "text": example["text"],
                    "label": example["label"],
                    "vector": vector,
                }
            )
        self._rebuild_matrix()

    def vote(self, text: str, k: int = 7) -> ModelVote:
        if not self.embedding_client:
            return ModelVote("embedding", "alert", 0.0, "embedding client unavailable", "semantic_embedding")
        if not self.items:
            return ModelVote("embedding", "alert", 0.0, "empty embedding index", "semantic_embedding")
        query = self.embedding_client.embed_texts([text])[0]
        top = self._top_matches(query, k)
        label_scores: defaultdict[str, float] = defaultdict(float)
        for score, label in top:
            label_scores[str(label)] += max(0.0, score)
        if not label_scores:
            return ModelVote("embedding", "alert", 0.0, "no positive semantic match", "semantic_embedding")
        decision, score = max(label_scores.items(), key=lambda item: item[1])
        total = sum(label_scores.values())
        confidence = score / total if total else 0.0
        reason = f"{self.provider}:{self.model}; top_sim={top[0][0]:.3f}, k={len(top)}"
        if self.vote_mode == "assist":
            return ModelVote("embedding", "alert", min(0.75, max(0.45, confidence)), reason, "semantic_embedding")
        return ModelVote("embedding", decision, confidence, reason, "semantic_embedding")

    def _top_matches(self, query: list[float], k: int) -> list[tuple[float, str]]:
        if np is not None and self._matrix is not None:
            scores = self._matrix @ np.asarray(query, dtype=np.float32)
            count = min(k, len(scores))
            if count <= 0:
                return []
            indexes = np.argpartition(scores, -count)[-count:]
            ordered = indexes[np.argsort(scores[indexes])[::-1]]
            return [(float(scores[index]), self._labels[int(index)]) for index in ordered]
        scored = [(dense_cosine(query, item["vector"]), str(item["label"])) for item in self.items]
        return sorted(scored, key=lambda item: item[0], reverse=True)[:k]

    def feature_stats(self, text: str, k: int = 7) -> list[float]:
        if not self.embedding_client or not self.items:
            return [0.0, 0.0, 0.0, 0.0]
        query = self.embedding_client.embed_texts([text])[0]
        top = self._top_matches(query, k)
        if not top:
            return [0.0, 0.0, 0.0, 0.0]
        label_scores: defaultdict[str, float] = defaultdict(float)
        for score, label in top:
            label_scores[str(label)] += max(0.0, score)
        total = sum(label_scores.values())
        fail_ratio = label_scores["fail"] / total if total else 0.0
        pass_ratio = label_scores["pass"] / total if total else 0.0
        return [float(top[0][0]), fail_ratio, pass_ratio, abs(fail_ratio - pass_ratio)]

    def similar_examples(self, text: str, k: int = 3) -> list[dict[str, Any]]:
        if not self.embedding_client or not self.items:
            return []
        query = self.embedding_client.embed_texts([text])[0]
        top = self._top_match_items(query, k)
        return [
            {
                "score": round(score, 4),
                "label": item.get("label"),
                "text": str(item.get("text", ""))[:120],
            }
            for score, item in top
        ]

    def _top_match_items(self, query: list[float], k: int) -> list[tuple[float, dict[str, Any]]]:
        if np is not None and self._matrix is not None:
            scores = self._matrix @ np.asarray(query, dtype=np.float32)
            count = min(k, len(scores))
            if count <= 0:
                return []
            indexes = np.argpartition(scores, -count)[-count:]
            ordered = indexes[np.argsort(scores[indexes])[::-1]]
            return [(float(scores[index]), self.items[int(index)]) for index in ordered]
        scored = [(dense_cosine(query, item["vector"]), item) for item in self.items]
        return sorted(scored, key=lambda item: item[0], reverse=True)[:k]

    def _rebuild_matrix(self) -> None:
        self._labels = [str(item["label"]) for item in self.items]
        if np is None or not self.items:
            self._matrix = None
            return
        self._matrix = np.asarray([item["vector"] for item in self.items], dtype=np.float32)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "vote_mode": self.vote_mode,
            "items": self.items,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        embedding_client: EmbeddingClient | None = None,
    ) -> "RemoteEmbeddingSafetyIndex":
        index = cls(
            embedding_client=embedding_client,
            provider=str(data.get("provider", "bigmodel")),
            model=str(data.get("model", "embedding-3")),
            vote_mode=str(data.get("vote_mode", "assist")),
        )
        index.items = data.get("items", [])
        index._rebuild_matrix()
        return index


class NaiveBayesSafetyClassifier:
    def __init__(self, vectorizer: CharNgramVectorizer | None = None, alpha: float = 1.0) -> None:
        self.vectorizer = vectorizer or CharNgramVectorizer(max_features=16000)
        self.alpha = alpha
        self.class_doc_counts: Counter[str] = Counter()
        self.class_term_counts: dict[str, Counter[str]] = {}
        self.class_total_terms: Counter[str] = Counter()

    def fit(self, examples: list[dict[str, str]]) -> None:
        self.vectorizer.fit(example["text"] for example in examples)
        self.class_doc_counts.clear()
        self.class_term_counts = {"pass": Counter(), "fail": Counter()}
        self.class_total_terms.clear()
        for example in examples:
            label = example["label"]
            self.class_doc_counts[label] += 1
            terms = self.vectorizer._ngrams(example["text"])
            terms = [term for term in terms if term in self.vectorizer.vocabulary]
            self.class_term_counts.setdefault(label, Counter()).update(terms)
            self.class_total_terms[label] += len(terms)

    def vote(self, text: str) -> ModelVote:
        terms = [term for term in self.vectorizer._ngrams(text) if term in self.vectorizer.vocabulary]
        if not terms:
            return ModelVote("naive_bayes", "alert", 0.0, "no known terms")
        total_docs = sum(self.class_doc_counts.values())
        vocab_size = max(1, len(self.vectorizer.vocabulary))
        log_probs: dict[str, float] = {}
        for label in ("pass", "fail"):
            prior = (self.class_doc_counts[label] + self.alpha) / (total_docs + 2 * self.alpha)
            log_prob = math.log(prior)
            denominator = self.class_total_terms[label] + self.alpha * vocab_size
            counts = self.class_term_counts.get(label, Counter())
            for term in terms:
                log_prob += math.log((counts[term] + self.alpha) / denominator)
            log_probs[label] = log_prob
        decision = max(log_probs, key=log_probs.get)
        confidence = sigmoid(abs(log_probs["fail"] - log_probs["pass"]) / max(1, len(terms)))
        return ModelVote("naive_bayes", decision, confidence, "char ngram classifier", "statistical_text")

    def to_dict(self) -> dict[str, Any]:
        return {
            "vectorizer": self.vectorizer.to_dict(),
            "alpha": self.alpha,
            "class_doc_counts": dict(self.class_doc_counts),
            "class_term_counts": {label: dict(counts) for label, counts in self.class_term_counts.items()},
            "class_total_terms": dict(self.class_total_terms),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NaiveBayesSafetyClassifier":
        classifier = cls(CharNgramVectorizer.from_dict(data["vectorizer"]), float(data["alpha"]))
        classifier.class_doc_counts = Counter(data["class_doc_counts"])
        classifier.class_term_counts = {
            label: Counter(counts) for label, counts in data["class_term_counts"].items()
        }
        classifier.class_total_terms = Counter(data["class_total_terms"])
        return classifier


class FeatureVectorizer:
    keyword_groups = {
        "prompt_attack": ["忽略", "系统提示词", "开发者消息", "隐藏提示", "system prompt"],
        "illegal": ["违法", "犯罪", "处罚", "定罪", "规避", "绕过", "伪造"],
        "hate": ["歧视", "仇恨", "侮辱", "低等", "地域黑"],
        "privacy": ["隐私", "身份证", "手机号", "住址", "人肉", "开盒"],
        "business": ["商业秘密", "知识产权", "刷单", "虚假宣传", "盗版"],
        "violence": ["暴力", "恐怖", "极端", "炸药", "枪支"],
        "national_security": ["国家安全", "颠覆", "间谍", "情报", "渗透", "境外", "分裂"],
        "cyber": ["黑客", "漏洞", "攻击", "网络安全", "物联网", "加密", "数据安全"],
    }

    def __init__(
        self,
        *,
        rule_auditor: AISecurityAuditor | None = None,
        vector_index: VectorSafetyIndex | None = None,
        embedding_index: RemoteEmbeddingSafetyIndex | None = None,
    ) -> None:
        self.rule_auditor = rule_auditor
        self.vector_index = vector_index
        self.embedding_index = embedding_index

    def bind_context(
        self,
        *,
        rule_auditor: AISecurityAuditor | None = None,
        vector_index: VectorSafetyIndex | None = None,
        embedding_index: RemoteEmbeddingSafetyIndex | None = None,
    ) -> None:
        if rule_auditor:
            self.rule_auditor = rule_auditor
        if vector_index:
            self.vector_index = vector_index
        if embedding_index:
            self.embedding_index = embedding_index

    def transform(self, text: str) -> list[float]:
        value = str(text or "")
        length = max(1, len(value))
        lowered = value.lower()
        rule_features = self._rule_features(value)
        vector_features = self.vector_index.feature_stats(value) if self.vector_index else [0.0, 0.0, 0.0, 0.0]
        embedding_features = (
            self.embedding_index.feature_stats(value) if self.embedding_index else [0.0, 0.0, 0.0, 0.0]
        )
        features = [
            len(value),
            value.count("?") + value.count("？"),
            sum(char.isdigit() for char in value),
            sum(ord(char) < 128 for char in value) / length,
            len(re.findall(r"[#`<>{}\[\]$\\/|]", value)) / length,
            len(re.findall(r"(如何|怎么|怎样|哪些|什么|是否|能否)", value)),
            len(re.findall(r"(处罚|定性|构成|认定|违法|犯罪|边界|合法性)", value)),
            *rule_features,
            *vector_features,
            *embedding_features,
        ]
        for keywords in self.keyword_groups.values():
            features.append(float(any(keyword.lower() in lowered for keyword in keywords)))
        return [float(item) for item in features]

    def feature_names(self) -> list[str]:
        return [
            "length",
            "question_mark_count",
            "digit_count",
            "ascii_ratio",
            "special_ratio",
            "question_intent_count",
            "legal_intent_count",
            "rule_score",
            "rule_finding_count",
            "rule_high_count",
            "rule_sensitive_lexicon_hit",
            "rule_max_score",
            "tfidf_top_sim",
            "tfidf_fail_neighbor_ratio",
            "tfidf_pass_neighbor_ratio",
            "tfidf_neighbor_margin",
            "embedding_top_sim",
            "embedding_fail_neighbor_ratio",
            "embedding_pass_neighbor_ratio",
            "embedding_neighbor_margin",
            *[f"kw_{name}" for name in self.keyword_groups],
        ]

    def to_dict(self) -> dict[str, Any]:
        return {"keyword_groups": self.keyword_groups}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeatureVectorizer":
        vectorizer = cls()
        if data.get("keyword_groups"):
            vectorizer.keyword_groups = {
                str(name): [str(keyword) for keyword in keywords]
                for name, keywords in data["keyword_groups"].items()
            }
        return vectorizer

    def _rule_features(self, text: str) -> list[float]:
        if not self.rule_auditor:
            return [0.0, 0.0, 0.0, 0.0, 0.0]
        result = self.rule_auditor.audit_request(text)
        findings = result.findings
        return [
            float(result.score),
            float(len(findings)),
            float(sum(1 for finding in findings if finding.severity == "high")),
            float(any(finding.category == "sensitive_lexicon" for finding in findings)),
            float(max((finding.score for finding in findings), default=0.0)),
        ]


class XGBoostSafetyClassifier:
    def __init__(self, feature_vectorizer: FeatureVectorizer | None = None) -> None:
        self.feature_vectorizer = feature_vectorizer or FeatureVectorizer()
        self.backend = "none"
        self.model: Any = None
        self.params: dict[str, Any] = {}

    def bind_context(
        self,
        *,
        rule_auditor: AISecurityAuditor | None = None,
        vector_index: VectorSafetyIndex | None = None,
        embedding_index: RemoteEmbeddingSafetyIndex | None = None,
    ) -> None:
        self.feature_vectorizer.bind_context(
            rule_auditor=rule_auditor,
            vector_index=vector_index,
            embedding_index=embedding_index,
        )

    def fit(self, examples: list[dict[str, str]]) -> None:
        features = [self.feature_vectorizer.transform(example["text"]) for example in examples]
        labels = [1 if example["label"] == "fail" else 0 for example in examples]
        try:
            import xgboost as xgb

            self.backend = "xgboost"
            self.params = {
                "objective": "binary:logistic",
                "eval_metric": "logloss",
                "eta": 0.08,
                "max_depth": 4,
                "subsample": 0.9,
                "colsample_bytree": 0.9,
                "seed": 42,
            }
            self.model = xgb.train(self.params, xgb.DMatrix(features, label=labels), num_boost_round=180)
        except Exception:
            if GradientBoostingClassifier is None:
                raise RuntimeError("Neither xgboost nor sklearn GradientBoostingClassifier is available")
            self.backend = "sklearn_gradient_boosting"
            self.params = {"n_estimators": 160, "learning_rate": 0.08, "max_depth": 3, "random_state": 42}
            self.model = GradientBoostingClassifier(**self.params)
            self.model.fit(features, labels)

    def vote(self, text: str) -> ModelVote:
        if not self.model:
            return ModelVote("xgboost", "alert", 0.0, "model unavailable", "tree_classifier")
        features = [self.feature_vectorizer.transform(text)]
        if self.backend == "xgboost":
            import xgboost as xgb

            fail_probability = float(self.model.predict(xgb.DMatrix(features))[0])
            pass_probability = 1.0 - fail_probability
        else:
            probability = self.model.predict_proba(features)[0]
            fail_probability = float(probability[1])
            pass_probability = float(probability[0])
        decision = "fail" if fail_probability >= pass_probability else "pass"
        confidence = max(fail_probability, pass_probability)
        reason = f"{self.backend}; fail_prob={fail_probability:.3f}"
        return ModelVote("xgboost", decision, confidence, reason, "tree_classifier")

    def to_dict(self) -> dict[str, Any]:
        if not self.model:
            return {}
        return {
            "backend": self.backend,
            "params": self.params,
            "feature_vectorizer": self.feature_vectorizer.to_dict(),
            "model": model_to_base64(self.model),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "XGBoostSafetyClassifier":
        classifier = cls(FeatureVectorizer.from_dict(data.get("feature_vectorizer", {})))
        classifier.backend = str(data.get("backend", "unknown"))
        classifier.params = data.get("params", {})
        classifier.model = model_from_base64(str(data["model"]))
        return classifier


class HybridSafetyAuditor:
    def __init__(
        self,
        *,
        rule_auditor: AISecurityAuditor | None = None,
        vector_index: VectorSafetyIndex | None = None,
        embedding_index: RemoteEmbeddingSafetyIndex | None = None,
        classifier: NaiveBayesSafetyClassifier | None = None,
        xgboost_classifier: XGBoostSafetyClassifier | None = None,
        cloud_threshold: float = 0.62,
        conflict_threshold: float = 0.18,
    ) -> None:
        self.rule_auditor = rule_auditor or AISecurityAuditor()
        self.vector_index = vector_index
        self.embedding_index = embedding_index
        self.classifier = classifier
        self.xgboost_classifier = xgboost_classifier
        if self.xgboost_classifier:
            self.xgboost_classifier.bind_context(
                rule_auditor=self.rule_auditor,
                vector_index=self.vector_index,
                embedding_index=self.embedding_index,
            )
        self.cloud_threshold = cloud_threshold
        self.conflict_threshold = conflict_threshold

    def audit_request(
        self,
        text: str,
        llm_vote: ModelVote | None = None,
        *,
        include_evidence: bool = True,
    ) -> HybridAuditResult:
        rule_result = self.rule_auditor.audit_request(text)
        votes = [
            ModelVote(
                "rules_regex_keywords",
                rule_result.decision.value,
                min(1.0, max(0.45, rule_result.score)),
                "; ".join(finding.category for finding in rule_result.findings[:3]),
                rule_result.findings[0].category if rule_result.findings else "rule_clear",
            )
        ]
        if self.vector_index:
            votes.append(self.vector_index.vote(text))
        if self.embedding_index:
            votes.append(self.embedding_index.vote(text))
        if self.classifier:
            votes.append(self.classifier.vote(text))
        if self.xgboost_classifier:
            votes.append(self.xgboost_classifier.vote(text))
        if llm_vote:
            votes.append(llm_vote)
        result = fuse_votes(
            votes,
            cloud_threshold=self.cloud_threshold,
            conflict_threshold=self.conflict_threshold,
        )
        evidence = self._build_evidence(text, rule_result) if include_evidence else {}
        if not llm_vote and self._needs_semantic_review(text, result):
            review_vote = ModelVote(
                "semantic_router",
                "alert",
                0.85,
                "strict safety taxonomy topic",
                "semantic_review",
            )
            return HybridAuditResult(
                decision=result.decision,
                confidence=result.confidence,
                votes=[*result.votes, review_vote],
                route="cloud",
                risk_type="semantic_review" if result.decision == "pass" else result.risk_type,
                explanation=f"{result.explanation}; route_hint=semantic_review",
                cloud_recommended=True,
                evidence=evidence,
            )
        return HybridAuditResult(
            decision=result.decision,
            confidence=result.confidence,
            votes=result.votes,
            route=result.route,
            risk_type=result.risk_type,
            explanation=result.explanation,
            cloud_recommended=result.cloud_recommended,
            evidence=evidence,
        )

    def _build_evidence(self, text: str, rule_result: Any) -> dict[str, Any]:
        return {
            "rules": [
                {
                    "category": finding.category,
                    "severity": finding.severity,
                    "evidence": finding.evidence,
                    "score": finding.score,
                }
                for finding in rule_result.findings[:8]
            ],
            "tfidf_similar_examples": self.vector_index.similar_examples(text) if self.vector_index else [],
            "embedding_similar_examples": self.embedding_index.similar_examples(text) if self.embedding_index else [],
        }

    def _needs_semantic_review(self, text: str, result: HybridAuditResult) -> bool:
        if result.route != "local":
            return False
        normalized = normalize_text(text)
        strict_topic = re.search(
            r"(国家安全|间谍|情报|舆论|渗透|颠覆|恐怖|反恐|黑客|漏洞|物联网|算法|"
            r"加密|量子|知识产权|生物安全|网络安全|经济安全|数据安全|境外|分裂|"
            r"煽动|心理操作|心理战|危害国家)",
            normalized,
        )
        review_intent = re.search(
            r"(如何|哪些|什么|是否|能否|边界|影响|挑战|威胁|手段|特征|利用|应对|"
            r"治理|防范|缓解|合法性|适用|处罚|定性|构成)",
            normalized,
        )
        return bool(strict_topic and review_intent)

    def save(self, path: Path) -> None:
        payload = {
            "vector_index": self.vector_index.to_dict() if self.vector_index else None,
            "embedding_index": self.embedding_index.to_dict() if self.embedding_index else None,
            "classifier": self.classifier.to_dict() if self.classifier else None,
            "xgboost_classifier": self.xgboost_classifier.to_dict() if self.xgboost_classifier else None,
            "routing": {
                "cloud_threshold": self.cloud_threshold,
                "conflict_threshold": self.conflict_threshold,
            },
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path, embedding_client: EmbeddingClient | None = None) -> "HybridSafetyAuditor":
        data = json.loads(path.read_text(encoding="utf-8"))
        vector_index = VectorSafetyIndex.from_dict(data["vector_index"]) if data.get("vector_index") else None
        embedding_index = (
            RemoteEmbeddingSafetyIndex.from_dict(data["embedding_index"], embedding_client=embedding_client)
            if data.get("embedding_index")
            else None
        )
        classifier = (
            NaiveBayesSafetyClassifier.from_dict(data["classifier"]) if data.get("classifier") else None
        )
        xgboost_classifier = (
            XGBoostSafetyClassifier.from_dict(data["xgboost_classifier"])
            if data.get("xgboost_classifier")
            else None
        )
        routing = data.get("routing", {})
        auditor = cls(
            vector_index=vector_index,
            embedding_index=embedding_index,
            classifier=classifier,
            xgboost_classifier=xgboost_classifier,
            cloud_threshold=float(routing.get("cloud_threshold", 0.62)),
            conflict_threshold=float(routing.get("conflict_threshold", 0.18)),
        )
        return auditor


def fuse_votes(
    votes: list[ModelVote],
    *,
    cloud_threshold: float = 0.62,
    conflict_threshold: float = 0.18,
) -> HybridAuditResult:
    weights = {
        "rules_regex_keywords": 0.95,
        "vector": 0.75,
        "embedding": 0.35,
        "naive_bayes": 0.80,
        "xgboost": 0.35,
    }
    totals: defaultdict[str, float] = defaultdict(float)
    active_votes: list[ModelVote] = []
    for vote in votes:
        if vote.decision not in {"pass", "fail", "alert"}:
            continue
        active_votes.append(vote)
        weight = weights.get(vote.source, 0.5)
        totals[vote.decision] += weight * max(0.05, min(1.0, vote.confidence))

    if totals["alert"] > max(totals["pass"], totals["fail"]):
        decision = "alert"
    else:
        decision = "fail" if totals["fail"] >= totals["pass"] else "pass"
    denominator = max(0.0001, totals["fail"] + totals["pass"] + totals["alert"])
    confidence = max(totals.values()) / denominator
    pass_score = totals["pass"]
    fail_score = totals["fail"]
    margin = abs(pass_score - fail_score) / denominator
    has_conflict = pass_score > 0 and fail_score > 0 and margin < conflict_threshold
    cloud_recommended = confidence < cloud_threshold or has_conflict
    route = "cloud" if cloud_recommended else "local"
    if totals["alert"] > max(pass_score, fail_score) and confidence < 0.75:
        route = "human_review"
        cloud_recommended = True

    risk_type = infer_risk_type(active_votes, decision)
    explanation = build_explanation(active_votes, decision, confidence, margin, route)
    return HybridAuditResult(
        decision=decision,
        confidence=round(confidence, 4),
        votes=votes,
        route=route,
        risk_type=risk_type,
        explanation=explanation,
        cloud_recommended=cloud_recommended,
        evidence={},
    )


def infer_risk_type(votes: list[ModelVote], decision: str) -> str:
    risk_counter: Counter[str] = Counter()
    for vote in votes:
        if vote.decision == decision and vote.risk_type:
            risk_counter[vote.risk_type] += max(1, int(vote.confidence * 10))
    if risk_counter:
        return risk_counter.most_common(1)[0][0]
    return "safe" if decision == "pass" else "unknown_risk"


def build_explanation(
    votes: list[ModelVote],
    decision: str,
    confidence: float,
    margin: float,
    route: str,
) -> str:
    supporters = [vote.source for vote in votes if vote.decision == decision]
    opponents = [vote.source for vote in votes if vote.decision not in {decision, "alert"}]
    parts = [
        f"decision={decision}",
        f"confidence={confidence:.3f}",
        f"margin={margin:.3f}",
        f"route={route}",
    ]
    if supporters:
        parts.append("supporters=" + ",".join(supporters))
    if opponents:
        parts.append("conflicts=" + ",".join(opponents))
    return "; ".join(parts)


def cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(term, 0.0) for term, value in left.items())


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def model_to_base64(model: Any) -> str:
    import base64
    import pickle

    return base64.b64encode(pickle.dumps(model)).decode("ascii")


def model_from_base64(value: str) -> Any:
    import base64
    import pickle

    return pickle.loads(base64.b64decode(value.encode("ascii")))
