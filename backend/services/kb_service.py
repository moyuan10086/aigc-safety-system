"""
知识库服务 — 文件上传、分块、向量化、RAG问答
"""
import uuid
from pathlib import Path
import httpx
import chromadb
from sentence_transformers import SentenceTransformer
from openai import OpenAI
from config import CHROMA_PATH, MLLM_API_KEY, MLLM_BASE_URL, MLLM_MODEL, PROXY_URL

_client = None
_collection = None
_embedder = None
_oai = None

KB_COLLECTION = "knowledge_base"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def _init():
    global _client, _collection, _embedder, _oai
    if _client is not None:
        return
    _client = chromadb.PersistentClient(path=CHROMA_PATH)
    _collection = _client.get_or_create_collection(KB_COLLECTION)
    _embedder = SentenceTransformer(
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        cache_folder=str(Path(__file__).parents[1] / "weights" / "sentence_transformers"),
        local_files_only=False,
    )
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
    chunks, start = [], 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return [c for c in chunks if c.strip()]


def add_file(file_path: str, filename: str, category: str = "默认") -> dict:
    _init()
    file_id = str(uuid.uuid4())
    text = _extract_text(file_path)
    chunks = _split(text)
    if not chunks:
        return {"file_id": file_id, "filename": filename, "chunks": 0}

    ids = [f"{file_id}_{i}" for i in range(len(chunks))]
    embeddings = _embedder.encode(chunks).tolist()
    metadatas = [{"file_id": file_id, "filename": filename, "chunk_index": i, "category": category}
                 for i in range(len(chunks))]
    _collection.add(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
    return {"file_id": file_id, "filename": filename, "chunks": len(chunks), "category": category}


def list_files(category: str = None) -> list[dict]:
    _init()
    result = _collection.get(include=["metadatas"])
    seen, files = set(), []
    for meta in result["metadatas"]:
        fid = meta["file_id"]
        if fid not in seen:
            if category and meta.get("category") != category:
                continue
            seen.add(fid)
            files.append({"file_id": fid, "filename": meta["filename"],
                          "category": meta.get("category", "默认")})
    return files


def list_chunks(file_id: str) -> list[dict]:
    _init()
    result = _collection.get(
        where={"file_id": file_id},
        include=["documents", "metadatas"]
    )
    return [
        {"chunk_id": cid, "chunk_index": meta["chunk_index"], "content": doc}
        for cid, doc, meta in zip(result["ids"], result["documents"], result["metadatas"])
    ]


def delete_file(file_id: str):
    _init()
    result = _collection.get(where={"file_id": file_id})
    if result["ids"]:
        _collection.delete(ids=result["ids"])


def query_stream(question: str, top_k: int = 3):
    """生成器：流式返回RAG问答结果"""
    _init()
    q_emb = _embedder.encode([question]).tolist()
    results = _collection.query(query_embeddings=q_emb, n_results=top_k)
    context = "\n\n".join(results["documents"][0]) if results["documents"] else ""

    messages = [
        {"role": "system", "content": "你是一个知识库问答助手，请根据以下参考内容回答用户问题。如果参考内容不足，请如实说明。"},
        {"role": "user", "content": f"参考内容：\n{context}\n\n问题：{question}"},
    ]
    stream = _oai.chat.completions.create(model=MLLM_MODEL, messages=messages, stream=True)
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
