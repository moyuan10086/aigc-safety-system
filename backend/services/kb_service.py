"""
知识库服务 — 文件上传、分块、向量化、RAG问答
"""
import math
import re
import uuid
from pathlib import Path
import httpx
import chromadb
from sentence_transformers import SentenceTransformer
from openai import OpenAI
from config import CHROMA_PATH, MLLM_API_KEY, MLLM_BASE_URL, MLLM_MODEL, PROXY_URL
from services.official_knowledge_sources import OFFICIAL_KNOWLEDGE_SOURCES

_client = None
_collection = None
_embedder = None
_oai = None

KB_COLLECTION = "knowledge_base_v2"
LEGACY_KB_COLLECTION = "knowledge_base"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
DEFAULT_TOP_K = 5
DEFAULT_SCORE_THRESHOLD = 0.32
USER_SOURCE_TYPE = "user_upload"
OFFICIAL_SOURCE_DIR = Path(__file__).parents[1] / "knowledge_sources"


def _init():
    global _client, _collection, _embedder, _oai
    if _client is not None:
        return
    _embedder = SentenceTransformer(
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        cache_folder=str(Path(__file__).parents[1] / "weights" / "sentence_transformers"),
        local_files_only=False,
    )
    _client = chromadb.PersistentClient(path=CHROMA_PATH)
    _collection = _client.get_or_create_collection(KB_COLLECTION, metadata={"hnsw:space": "cosine"})
    if _collection.count() == 0:
        try:
            legacy = _client.get_collection(LEGACY_KB_COLLECTION)
            existing = legacy.get(include=["documents", "metadatas"])
            documents = existing.get("documents") or []
            if documents:
                embeddings = _embedder.encode(documents, normalize_embeddings=True).tolist()
                _collection.add(
                    ids=existing["ids"], documents=documents,
                    metadatas=existing["metadatas"], embeddings=embeddings,
                )
        except Exception:
            pass
    if PROXY_URL:
        _oai = OpenAI(api_key=MLLM_API_KEY, base_url=MLLM_BASE_URL,
                      http_client=httpx.Client(proxy=PROXY_URL, timeout=60))
    else:
        _oai = OpenAI(api_key=MLLM_API_KEY, base_url=MLLM_BASE_URL)


def _extract_text(path: str) -> str:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".txt":
        return p.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".pdf":
        import pypdf
        reader = pypdf.PdfReader(str(p))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        from services.ocr_service import is_garbled, ocr_pdf
        if is_garbled(text):
            text = ocr_pdf(str(p))
        return text
    if suffix in (".docx", ".doc"):
        import docx
        doc = docx.Document(str(p))
        return "\n".join(p.text for p in doc.paragraphs)
    return p.read_text(encoding="utf-8", errors="ignore")


def _split(text: str) -> list[str]:
    """Paragraph-aware chunking with bounded overlap for Chinese documents."""
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+|(?<=[。！？；])\s*", text) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > CHUNK_SIZE:
            if current:
                chunks.append(current)
                current = ""
            step = CHUNK_SIZE - CHUNK_OVERLAP
            chunks.extend(paragraph[start:start + CHUNK_SIZE] for start in range(0, len(paragraph), step))
            continue
        candidate = f"{current}\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= CHUNK_SIZE:
            current = candidate
        else:
            chunks.append(current)
            overlap = current[-CHUNK_OVERLAP:] if current else ""
            current = f"{overlap}\n{paragraph}".strip()
    if current:
        chunks.append(current)
    return [chunk for chunk in chunks if chunk.strip()]


def _terms(text: str) -> set[str]:
    normalized = text.lower()
    words = set(re.findall(r"[a-z0-9_]{2,}|[\u4e00-\u9fff]", normalized))
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", normalized))
    words.update(chinese[index:index + 2] for index in range(max(0, len(chinese) - 1)))
    return {word for word in words if word}


def _lexical_score(query: str, document: str) -> float:
    query_terms = _terms(query)
    if not query_terms:
        return 0.0
    document_terms = _terms(document)
    overlap = query_terms & document_terms
    coverage = len(overlap) / len(query_terms)
    density = len(overlap) / max(1, math.sqrt(len(document_terms)))
    return min(1.0, coverage * 0.8 + density * 0.2)


def add_file(file_path: str, filename: str, category: str = "默认") -> dict:
    _init()
    file_id = str(uuid.uuid4())
    text = _extract_text(file_path)
    chunks = _split(text)
    if not chunks:
        return {"file_id": file_id, "filename": filename, "chunks": 0}

    ids = [f"{file_id}_{i}" for i in range(len(chunks))]
    embeddings = _embedder.encode(chunks, normalize_embeddings=True).tolist()
    metadatas = [{
        "file_id": file_id, "filename": filename, "title": filename,
        "chunk_index": i, "category": category, "publisher": "用户上传",
        "source_type": USER_SOURCE_TYPE, "document_type": "user_document",
        "source_url": "", "source_id": file_id, "summary": "用户上传资料",
        "managed": False,
    }
                 for i in range(len(chunks))]
    _collection.add(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
    return {"file_id": file_id, "filename": filename, "chunks": len(chunks), "category": category}


def _source_metadata(source: dict, chunk_index: int) -> dict:
    return {
        "file_id": f"official:{source['source_id']}",
        "filename": source["title"],
        "title": source["title"],
        "chunk_index": chunk_index,
        "category": source["category"],
        "publisher": source["publisher"],
        "source_type": "curated_official",
        "document_type": source["document_type"],
        "source_url": source["source_url"],
        "source_id": source["source_id"],
        "summary": source["summary"],
        "updated_at": source["updated_at"],
        "managed": True,
        "has_full_text": bool(source.get("local_filename")),
    }


def seed_official_sources() -> dict:
    """Idempotently add curated public-source summaries without touching uploads."""
    _init()
    added_sources = skipped_sources = added_chunks = 0
    for source in OFFICIAL_KNOWLEDGE_SOURCES:
        file_id = f"official:{source['source_id']}"
        existing = _collection.get(where={"file_id": file_id})
        if existing.get("ids"):
            skipped_sources += 1
            continue
        full_text = ""
        local_filename = source.get("local_filename")
        if local_filename:
            local_path = OFFICIAL_SOURCE_DIR / local_filename
            if local_path.is_file():
                full_text = _extract_text(str(local_path))
        chunks = _split(
            f"{source['title']}\n\n{source['summary']}\n\n{source['content']}"
            + (f"\n\n官方文件正文：\n{full_text}" if full_text else "")
        )
        ids = [f"{file_id}:{index}" for index in range(len(chunks))]
        embeddings = _embedder.encode(chunks, normalize_embeddings=True).tolist()
        _collection.add(
            ids=ids, embeddings=embeddings, documents=chunks,
            metadatas=[_source_metadata(source, index) for index in range(len(chunks))],
        )
        added_sources += 1
        added_chunks += len(chunks)
    return {
        "total_sources": len(OFFICIAL_KNOWLEDGE_SOURCES),
        "added_sources": added_sources,
        "skipped_sources": skipped_sources,
        "added_chunks": added_chunks,
    }


def list_files(category: str = None) -> list[dict]:
    _init()
    result = _collection.get(include=["metadatas"])
    grouped: dict[str, dict] = {}
    for meta in result["metadatas"]:
        fid = meta["file_id"]
        if category and meta.get("category") != category:
            continue
        if fid not in grouped:
            grouped[fid] = {
                "file_id": fid,
                "filename": meta.get("filename", "未知来源"),
                "title": meta.get("title", meta.get("filename", "未知来源")),
                "category": meta.get("category", "默认"),
                "publisher": meta.get("publisher", "用户上传"),
                "source_type": meta.get("source_type", USER_SOURCE_TYPE),
                "document_type": meta.get("document_type", "user_document"),
                "source_url": meta.get("source_url", ""),
                "source_id": meta.get("source_id", fid),
                "summary": meta.get("summary", ""),
                "updated_at": meta.get("updated_at", ""),
                "managed": bool(meta.get("managed", False)),
                "has_full_text": bool(meta.get("has_full_text", False)),
                "chunk_count": 0,
            }
        grouped[fid]["chunk_count"] += 1
    return sorted(
        grouped.values(),
        key=lambda item: (item["source_type"] != "curated_official", item["category"], item["title"]),
    )


def list_chunks(file_id: str) -> list[dict]:
    _init()
    result = _collection.get(
        where={"file_id": file_id},
        include=["documents", "metadatas"]
    )
    return [
        {
            "chunk_id": cid, "chunk_index": meta["chunk_index"], "content": doc,
            "publisher": meta.get("publisher", "用户上传"),
            "source_url": meta.get("source_url", ""),
            "category": meta.get("category", "默认"),
        }
        for cid, doc, meta in zip(result["ids"], result["documents"], result["metadatas"])
    ]


def delete_file(file_id: str) -> bool:
    _init()
    result = _collection.get(where={"file_id": file_id}, include=["metadatas"])
    if any(bool(meta.get("managed")) for meta in (result.get("metadatas") or [])):
        return False
    if result["ids"]:
        _collection.delete(ids=result["ids"])
    return True


def search(question: str, top_k: int = DEFAULT_TOP_K, category: str | None = None,
           score_threshold: float = DEFAULT_SCORE_THRESHOLD) -> dict:
    """Hybrid vector/lexical retrieval with explainable fused ranking."""
    _init()
    top_k = max(1, min(int(top_k), 20))
    where = {"category": category} if category else None
    collection_count = _collection.count()
    if collection_count == 0:
        return {
            "query": question, "retrieval_mode": "hybrid_vector_lexical",
            "rerank_mode": "weighted_fusion", "top_k": top_k,
            "score_threshold": score_threshold, "category_filter": category,
            "candidate_count": 0, "hits": [],
        }
    query_embedding = _embedder.encode([question], normalize_embeddings=True).tolist()
    vector = _collection.query(
        query_embeddings=query_embedding,
        n_results=min(collection_count, max(top_k * 4, 12)),
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    rows: dict[str, dict] = {}
    ids = vector.get("ids", [[]])[0]
    documents = vector.get("documents", [[]])[0]
    metadatas = vector.get("metadatas", [[]])[0]
    distances = vector.get("distances", [[]])[0]
    for chunk_id, document, metadata, distance in zip(ids, documents, metadatas, distances):
        vector_score = max(0.0, 1.0 - float(distance))
        lexical_score = _lexical_score(question, document)
        fused_score = vector_score * 0.7 + lexical_score * 0.3
        rows[chunk_id] = {
            "chunk_id": chunk_id,
            "content": document,
            "metadata": metadata or {},
            "vector_score": round(vector_score, 4),
            "keyword_score": round(lexical_score, 4),
            "score": round(fused_score, 4),
        }
    ranked = sorted(rows.values(), key=lambda item: item["score"], reverse=True)
    hits = []
    for item in ranked:
        if item["score"] < score_threshold:
            continue
        metadata = item.pop("metadata")
        item.update({
            "rank": len(hits) + 1,
            "filename": metadata.get("filename", "未知来源"),
            "category": metadata.get("category", "默认"),
            "chunk_index": metadata.get("chunk_index"),
            "snippet": item.pop("content")[:600],
            "publisher": metadata.get("publisher", "用户上传"),
            "source_url": metadata.get("source_url", ""),
            "document_type": metadata.get("document_type", "user_document"),
            "source_type": metadata.get("source_type", USER_SOURCE_TYPE),
            "summary": metadata.get("summary", ""),
        })
        hits.append(item)
        if len(hits) >= top_k:
            break
    return {
        "query": question,
        "retrieval_mode": "hybrid_vector_lexical",
        "rerank_mode": "weighted_fusion",
        "top_k": top_k,
        "score_threshold": score_threshold,
        "category_filter": category,
        "candidate_count": len(rows),
        "hits": hits,
    }


def stats() -> dict:
    _init()
    result = _collection.get(include=["metadatas"])
    metadatas = result.get("metadatas") or []
    files = {meta.get("file_id") for meta in metadatas if meta.get("file_id")}
    categories = sorted({meta.get("category", "默认") for meta in metadatas})
    official_sources = {
        meta.get("file_id") for meta in metadatas
        if meta.get("source_type") == "curated_official"
    }
    publishers = sorted({meta.get("publisher") for meta in metadatas if meta.get("publisher")})
    return {
        "engine": "RAG hybrid retrieval",
        "vector_store": "ChromaDB",
        "pipeline": "embedding → hybrid retrieval → weighted rerank → evidence",
        "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",
        "retrieval_mode": "hybrid_vector_lexical",
        "rerank_mode": "weighted_fusion",
        "chunk_strategy": "paragraph_aware",
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "file_count": len(files),
        "chunk_count": len(metadatas),
        "categories": categories,
        "official_source_count": len(official_sources),
        "user_source_count": max(0, len(files) - len(official_sources)),
        "publishers": publishers,
        "score_threshold": DEFAULT_SCORE_THRESHOLD,
    }


def query_stream(question: str, top_k: int = 3):
    """生成器：流式返回RAG问答结果"""
    _init()
    retrieval = search(question, top_k=top_k)
    context = "\n\n".join(
        f"[{hit['rank']}] {hit['filename']} / 分块 {hit['chunk_index']}\n{hit['snippet']}"
        for hit in retrieval["hits"]
    )

    messages = [
        {"role": "system", "content": "你是安全知识库问答助手。只能根据参考内容回答；证据不足时明确说明。关键结论必须使用 [1] [2] 形式标注引用，不得编造来源。"},
        {"role": "user", "content": f"参考内容：\n{context}\n\n问题：{question}"},
    ]
    stream = _oai.chat.completions.create(model=MLLM_MODEL, messages=messages, stream=True)
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
