import os
import re
from typing import Any, Dict, List
from uuid import uuid4

import chromadb
from langchain.schema import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_openai import OpenAIEmbeddings

RUNTIME_ENV_KEYS = {
    "gemini_api_key": "GEMINI_API_KEY",
    "openai_api_key": "OPENAI_API_KEY",
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "rag_llm_provider": "RAG_LLM_PROVIDER",
    "rag_embedding_provider": "RAG_EMBEDDING_PROVIDER",
    "rag_gemini_model": "RAG_GEMINI_MODEL",
    "rag_claude_model": "RAG_CLAUDE_MODEL",
    "rag_gemini_embedding_model": "RAG_GEMINI_EMBEDDING_MODEL",
    "rag_openai_embedding_model": "RAG_OPENAI_EMBEDDING_MODEL",
}


def get_runtime_config(mask_secrets: bool = False) -> Dict[str, Any]:
    config: Dict[str, Any] = {
        "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "rag_llm_provider": (os.getenv("RAG_LLM_PROVIDER", "gemini") or "gemini").strip().lower(),
        "rag_embedding_provider": (os.getenv("RAG_EMBEDDING_PROVIDER", "gemini") or "gemini").strip().lower(),
        "rag_gemini_model": os.getenv("RAG_GEMINI_MODEL", "gemini-1.5-flash"),
        "rag_claude_model": os.getenv("RAG_CLAUDE_MODEL", "claude-3-5-sonnet-20240620"),
        "rag_gemini_embedding_model": os.getenv("RAG_GEMINI_EMBEDDING_MODEL", "models/embedding-001"),
        "rag_openai_embedding_model": os.getenv("RAG_OPENAI_EMBEDDING_MODEL", "text-embedding-3-large"),
    }

    if not mask_secrets:
        return config

    def mask(value: str) -> str:
        if not value:
            return ""
        if len(value) <= 6:
            return "*" * len(value)
        return f"{value[:3]}{'*' * (len(value) - 6)}{value[-3:]}"

    masked = dict(config)
    masked["gemini_api_key"] = mask(config["gemini_api_key"])
    masked["openai_api_key"] = mask(config["openai_api_key"])
    masked["anthropic_api_key"] = mask(config["anthropic_api_key"])
    return masked


def _reset_runtime_clients() -> None:
    global _embeddings, _llm
    _embeddings = None
    _llm = None


def update_runtime_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    for key, env_key in RUNTIME_ENV_KEYS.items():
        if key not in updates:
            continue
        value = updates[key]
        if value is None:
            continue
        value_str = str(value).strip()
        os.environ[env_key] = value_str

    _reset_runtime_clients()
    return get_runtime_config(mask_secrets=True)


def _build_chroma_client() -> chromadb.ClientAPI:
    chroma_path = os.getenv("CHROMA_PATH", "/app/chroma_db")
    chroma_host = os.getenv("CHROMA_HOST", "")
    chroma_port = int(os.getenv("CHROMA_PORT", "8000"))
    try:
        if chroma_host:
            return chromadb.HttpClient(host=chroma_host, port=chroma_port)
        return chromadb.PersistentClient(path=chroma_path)
    except Exception as exc:
        raise RuntimeError(f"Failed to initialize Chroma client: {exc}") from exc


_chroma_client: chromadb.ClientAPI | None = None
_collection: Any | None = None


def _get_client() -> chromadb.ClientAPI:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = _build_chroma_client()
    return _chroma_client


def _get_collection() -> Any:
    chroma_collection = os.getenv("CHROMA_COLLECTION", "documents")
    try:
        global _collection
        if _collection is None:
            _collection = _get_client().get_or_create_collection(name=chroma_collection)
        return _collection
    except Exception as exc:
        raise RuntimeError(f"Failed to access Chroma collection '{chroma_collection}': {exc}") from exc


_embeddings: Any | None = None


def _build_embeddings() -> Any:
    cfg = get_runtime_config(mask_secrets=False)

    if cfg["rag_embedding_provider"] == "openai":
        if not cfg["openai_api_key"]:
            raise ValueError("OPENAI_API_KEY is not configured")
        return OpenAIEmbeddings(
            model=cfg["rag_openai_embedding_model"],
            openai_api_key=cfg["openai_api_key"],
        )

    if cfg["rag_embedding_provider"] == "gemini":
        if not cfg["gemini_api_key"]:
            raise ValueError("GEMINI_API_KEY is not configured")
        return GoogleGenerativeAIEmbeddings(
            model=cfg["rag_gemini_embedding_model"],
            google_api_key=cfg["gemini_api_key"],
        )

    raise ValueError(f"Unsupported RAG_EMBEDDING_PROVIDER: {cfg['rag_embedding_provider']}")


def _get_embeddings() -> Any:
    global _embeddings
    if _embeddings is None:
        _embeddings = _build_embeddings()
    return _embeddings


def _build_llm() -> Any:
    cfg = get_runtime_config(mask_secrets=False)

    if cfg["rag_llm_provider"] == "claude":
        if not cfg["anthropic_api_key"]:
            raise ValueError("ANTHROPIC_API_KEY is not configured")
        try:
            from langchain_anthropic import ChatAnthropic
        except Exception as exc:
            raise RuntimeError(
                "Claude provider requires 'langchain-anthropic'. Install dependency first"
            ) from exc
        return ChatAnthropic(
            model=cfg["rag_claude_model"],
            anthropic_api_key=cfg["anthropic_api_key"],
            temperature=0.3,
        )

    # Default provider: Gemini
    if not cfg["gemini_api_key"]:
        raise ValueError("GEMINI_API_KEY is not configured")
    return ChatGoogleGenerativeAI(
        model=cfg["rag_gemini_model"],
        temperature=0.3,
        google_api_key=cfg["gemini_api_key"],
    )


_llm: Any | None = None


def _get_llm() -> Any:
    global _llm
    if _llm is None:
        _llm = _build_llm()
    return _llm


def add_documents_to_vector_db(chunks: List[str], person_id: int, document_name: str = "") -> int:
    """Store chunks in Chroma with embeddings and person metadata."""
    embeddings = _get_embeddings()

    normalized_chunks = [chunk.strip() for chunk in chunks if chunk and chunk.strip()]
    if not normalized_chunks:
        raise ValueError("No non-empty chunks provided")

    try:
        vectors = embeddings.embed_documents(normalized_chunks)
    except Exception as exc:
        raise RuntimeError(f"Embedding generation failed: {exc}") from exc

    uid = uuid4().hex
    ids = [f"person_{person_id}_{uid}_{idx}" for idx in range(len(normalized_chunks))]
    metadatas = [
        {
            "person_id": int(person_id),
            "chunk_index": idx,
            "document_name": document_name or "unknown",
        }
        for idx in range(len(normalized_chunks))
    ]

    try:
        collection = _get_collection()
        collection.add(
            ids=ids,
            documents=normalized_chunks,
            embeddings=vectors,
            metadatas=metadatas,
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to write chunks to ChromaDB: {exc}") from exc

    return len(normalized_chunks)


def search_documents(query: str, top_k: int = 3) -> Dict[str, List[Any]]:
    """Run vector similarity search and return documents + metadatas."""
    embeddings = _get_embeddings()

    if not query or not query.strip():
        raise ValueError("Query must not be empty")

    try:
        collection = _get_collection()
        query_vector = embeddings.embed_query(query)
        results = collection.query(query_embeddings=[query_vector], n_results=max(1, top_k))
    except Exception as exc:
        raise RuntimeError(f"Chroma similarity search failed: {exc}") from exc

    documents = (results.get("documents") or [[]])[0]
    metadatas = (results.get("metadatas") or [[]])[0]

    return {"documents": documents, "metadatas": metadatas}


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[\w-]+", (text or "").lower()) if len(t) > 2}


def _lexical_score(query: str, doc: str) -> float:
    q = _tokenize(query)
    d = _tokenize(doc)
    if not q or not d:
        return 0.0
    intersection = len(q.intersection(d))
    return intersection / max(1, len(q))


def _distance_to_similarity(distance: Any) -> float:
    try:
        d = float(distance)
    except Exception:
        return 0.0
    if d < 0:
        d = 0.0
    return 1.0 / (1.0 + d)


def search_documents_ranked(
    query: str,
    top_k: int = 4,
    candidate_k: int = 16,
    min_score: float = 0.2,
    person_id: int | None = None,
) -> Dict[str, List[Any]]:
    """Retrieve candidates, rerank by hybrid score, and return filtered context docs."""
    embeddings = _get_embeddings()

    if not query or not query.strip():
        raise ValueError("Query must not be empty")

    where_filter = {"person_id": int(person_id)} if person_id is not None else None

    try:
        collection = _get_collection()
        query_vector = embeddings.embed_query(query)
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=max(top_k, candidate_k),
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as exc:
        raise RuntimeError(f"Chroma similarity search failed: {exc}") from exc

    documents = (results.get("documents") or [[]])[0]
    metadatas = (results.get("metadatas") or [[]])[0]
    distances = (results.get("distances") or [[]])[0]

    candidates: list[dict] = []
    for idx, doc in enumerate(documents):
        meta = metadatas[idx] if idx < len(metadatas) and isinstance(metadatas[idx], dict) else {}
        distance = distances[idx] if idx < len(distances) else None

        semantic = _distance_to_similarity(distance)
        lexical = _lexical_score(query, doc)
        hybrid = 0.75 * semantic + 0.25 * lexical

        candidates.append(
            {
                "document": doc,
                "metadata": meta,
                "score": hybrid,
            }
        )

    ranked = sorted(candidates, key=lambda x: x["score"], reverse=True)
    filtered = [row for row in ranked if row["score"] >= min_score][: max(1, top_k)]

    return {
        "documents": [row["document"] for row in filtered],
        "metadatas": [row["metadata"] for row in filtered],
        "scores": [round(float(row["score"]), 4) for row in filtered],
    }


def generate_answer(query: str, context_docs: List[str], language: str = "") -> str:
    """Generate a strict context-only answer for a user query."""
    llm = _get_llm()

    if not context_docs:
        return "Недостаточно данных в контексте, чтобы ответить на вопрос."

    context = "\n\n".join(f"Фрагмент {idx + 1}: {chunk}" for idx, chunk in enumerate(context_docs))

    system_prompt = (
        "Ты архивный ассистент. Отвечай ТОЛЬКО по переданному контексту. Если пользователь спрашивает на кыргызском, отвечай на кыргызском если на турецком то отвечай на турецком"
        "Используй только факты из фрагментов, даже если данные синтетические/учебные. "
        "Не добавляй внешние знания. Если данных недостаточно, ответь: "
        "'Недостаточно данных в контексте'. "
        "Пиши кратко и по существу."
    )
    user_prompt = f"Контекст:\n{context}\n\nВопрос: {query}"

    try:
        response = llm.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )
    except Exception as exc:
        raise RuntimeError(f"LLM generation failed: {exc}") from exc

    return response.content.strip() if response.content else ""


def answer_with_rag(
    query: str,
    top_k: int = 4,
    candidate_k: int = 16,
    min_score: float = 0.2,
    person_id: int | None = None,
) -> Dict[str, Any]:
    """Full RAG pipeline: retrieve ranked context, answer, and return sources + citations."""
    search_result = search_documents_ranked(
        query=query,
        top_k=top_k,
        candidate_k=candidate_k,
        min_score=min_score,
        person_id=person_id,
    )
    docs = search_result["documents"]
    metas = search_result["metadatas"]
    scores = search_result.get("scores", [])

    if not docs:
        return {
            "answer": "Информация по запросу не найдена в загруженных документах.",
            "sources": [],
            "citations": [],
        }

    answer = generate_answer(query=query, context_docs=docs)

    sources: List[int] = []
    citations: List[dict] = []
    for meta in metas:
        person_id = meta.get("person_id") if isinstance(meta, dict) else None
        if isinstance(person_id, int):
            sources.append(person_id)
        elif isinstance(person_id, str) and person_id.isdigit():
            sources.append(int(person_id))

    for idx, doc in enumerate(docs):
        meta = metas[idx] if idx < len(metas) and isinstance(metas[idx], dict) else {}
        pid = meta.get("person_id")
        person_value = int(pid) if isinstance(pid, str) and pid.isdigit() else pid
        citations.append(
            {
                "person_id": person_value,
                "document_name": meta.get("document_name") or "unknown",
                "chunk_index": meta.get("chunk_index"),
                "score": scores[idx] if idx < len(scores) else None,
                "quote": (doc or "")[:300],
            }
        )

    unique_sources = sorted(set(sources))
    return {"answer": answer, "sources": unique_sources, "citations": citations}
