import os
from typing import Any, Dict, List
from uuid import uuid4

import chromadb
from langchain.schema import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
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


embeddings = (
    GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=GEMINI_API_KEY)
    if GEMINI_API_KEY
    else None
)
llm = (
    ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.3, google_api_key=GEMINI_API_KEY)
    if GEMINI_API_KEY
    else None
)


def add_documents_to_vector_db(chunks: List[str], person_id: int, document_name: str = "") -> int:
    """Store chunks in Chroma with embeddings and person metadata."""
    if not GEMINI_API_KEY or embeddings is None:
        raise ValueError("GEMINI_API_KEY is not configured")

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
    if not GEMINI_API_KEY or embeddings is None:
        raise ValueError("GEMINI_API_KEY is not configured")

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


def generate_answer(query: str, context_docs: List[str], language: str = "") -> str:
    """Generate a strict context-only answer for a user query."""
    if not GEMINI_API_KEY or llm is None:
        raise ValueError("GEMINI_API_KEY is not configured")

    if not context_docs:
        return "Недостаточно данных в контексте, чтобы ответить на вопрос."

    context = "\n\n".join(f"Фрагмент {idx + 1}: {chunk}" for idx, chunk in enumerate(context_docs))

    system_prompt = (
        "Отвечай ТОЛЬКО по контексту. "
        "Данные могут быть выдуманными, не используй знания из интернета. "
        "Если в контексте нет ответа, прямо скажи, что информации недостаточно."
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


def answer_with_rag(query: str, top_k: int = 3) -> Dict[str, Any]:
    """Full RAG pipeline: retrieve context, answer, and return source person IDs."""
    search_result = search_documents(query=query, top_k=top_k)
    docs = search_result["documents"]
    metas = search_result["metadatas"]

    if not docs:
        return {"answer": "Информация по запросу не найдена в загруженных документах.", "sources": []}

    answer = generate_answer(query=query, context_docs=docs)

    sources: List[int] = []
    for meta in metas:
        person_id = meta.get("person_id") if isinstance(meta, dict) else None
        if isinstance(person_id, int):
            sources.append(person_id)
        elif isinstance(person_id, str) and person_id.isdigit():
            sources.append(int(person_id))

    unique_sources = sorted(set(sources))
    return {"answer": answer, "sources": unique_sources}
