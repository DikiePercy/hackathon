import os
import re
from typing import Any, Dict, List
from uuid import uuid4

import chromadb
from langchain.schema import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
RAG_LLM_PROVIDER = (os.getenv("RAG_LLM_PROVIDER", "gemini") or "gemini").strip().lower()
RAG_EMBEDDING_PROVIDER = (os.getenv("RAG_EMBEDDING_PROVIDER", "gemini") or "gemini").strip().lower()
RAG_GEMINI_MODEL = os.getenv("RAG_GEMINI_MODEL", "gemini-1.5-flash")
RAG_CLAUDE_MODEL = os.getenv("RAG_CLAUDE_MODEL", "claude-3-5-sonnet-20240620")
RAG_GEMINI_EMBEDDING_MODEL = os.getenv("RAG_GEMINI_EMBEDDING_MODEL", "models/embedding-001")
RAG_OPENAI_EMBEDDING_MODEL = os.getenv("RAG_OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
RAG_OLLAMA_MODEL = os.getenv("RAG_OLLAMA_MODEL", "llama3:8b")
CHROMA_PATH = os.getenv("CHROMA_PATH", "/app/chroma_db")
CHROMA_HOST = os.getenv("CHROMA_HOST", "")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "documents")


def _build_chroma_client() -> chromadb.ClientAPI:
    try:
        if CHROMA_HOST:
            return chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        return chromadb.PersistentClient(path=CHROMA_PATH)
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
    try:
        global _collection
        if _collection is None:
            _collection = _get_client().get_or_create_collection(name=CHROMA_COLLECTION)
        return _collection
    except Exception as exc:
        raise RuntimeError(f"Failed to access Chroma collection '{CHROMA_COLLECTION}': {exc}") from exc


_embeddings: Any | None = None


def _build_embeddings() -> Any:
    if RAG_EMBEDDING_PROVIDER == "ollama":
        try:
            from langchain_community.embeddings import OllamaEmbeddings
        except ImportError:
            raise RuntimeError("Ollama provider requires 'langchain-community'.")
        return OllamaEmbeddings(
            base_url=OLLAMA_BASE_URL,
            model=RAG_OLLAMA_MODEL,
        )

    if RAG_EMBEDDING_PROVIDER == "gemini":
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not configured")
        return GoogleGenerativeAIEmbeddings(
            model=RAG_GEMINI_EMBEDDING_MODEL,
            google_api_key=GEMINI_API_KEY,
        )

    raise ValueError(f"Unsupported RAG_EMBEDDING_PROVIDER: {RAG_EMBEDDING_PROVIDER}")


def _get_embeddings() -> Any:
    global _embeddings
    if _embeddings is None:
        _embeddings = _build_embeddings()
    return _embeddings


def _build_llm() -> Any:
    if RAG_LLM_PROVIDER == "ollama":
        try:
            from langchain_community.llms import Ollama
        except ImportError:
            raise RuntimeError("Ollama provider requires 'langchain-community'.")
        return Ollama(
            base_url=OLLAMA_BASE_URL,
            model=RAG_OLLAMA_MODEL,
            temperature=0.3,
        )

    if RAG_LLM_PROVIDER == "claude":
        if not ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY is not configured")
        try:
            from langchain_anthropic import ChatAnthropic
        except Exception as exc:
            raise RuntimeError(
                "Claude provider requires 'langchain-anthropic'. Install dependency first"
            ) from exc
        return ChatAnthropic(
            model=RAG_CLAUDE_MODEL,
            anthropic_api_key=ANTHROPIC_API_KEY,
            temperature=0.3,
        )

    # Default provider: Gemini
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not configured")
    return ChatGoogleGenerativeAI(
        model=RAG_GEMINI_MODEL,
        temperature=0.3,
        google_api_key=GEMINI_API_KEY,
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
        # Check if LLM is chat model (supports messages) or simple LLM (supports string prompt)
        llm_class_name = type(llm).__name__
        if "Chat" in llm_class_name or hasattr(llm, "invoke") and "Anthropic" in llm_class_name:
            # Chat models like ChatGoogleGenerativeAI, ChatAnthropic
            response = llm.invoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
            )
            return response.content.strip() if hasattr(response, 'content') and response.content else str(response).strip()
        else:
            # Simple LLM like Ollama
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            response = llm.invoke(full_prompt)
            # Response from Ollama is usually a string
            return response.strip() if isinstance(response, str) else str(response).strip()
    except Exception as exc:
        raise RuntimeError(f"LLM generation failed: {exc}") from exc



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

def get_runtime_config() -> Dict[str, Any]:
    """Return current RAG configuration for frontend/admin."""
    return {
        "llm_provider": RAG_LLM_PROVIDER,
        "embedding_provider": RAG_EMBEDDING_PROVIDER,
        "model": RAG_OLLAMA_MODEL if RAG_LLM_PROVIDER == "ollama" else "gemini"
    }

def update_runtime_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Stub to support old code. Local RAG doesn't update config via API."""
    return get_runtime_config()