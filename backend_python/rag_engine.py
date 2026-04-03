import os
from typing import List, Dict
from uuid import uuid4
import chromadb
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
CHROMA_PATH = os.getenv("CHROMA_PATH", "/app/chroma_db")
CHROMA_HOST = os.getenv("CHROMA_HOST", "")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "documents")

# Initialize ChromaDB client
if CHROMA_HOST:
    chroma_client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
else:
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)

# Get or create collection
try:
    collection = chroma_client.get_collection(name=CHROMA_COLLECTION)
except Exception:
    collection = chroma_client.create_collection(name=CHROMA_COLLECTION)

# Initialize embeddings
embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Initialize LLM
llm = ChatOpenAI(
    model="gpt-3.5-turbo",
    temperature=0.7,
    openai_api_key=OPENAI_API_KEY
) if OPENAI_API_KEY else None


def add_documents_to_vector_db(chunks: List[str], person_id: int, document_name: str):
    """Add document chunks to ChromaDB with person_id metadata"""
    if not embeddings:
        raise ValueError("OpenAI API key not configured")
    
    # Generate embeddings
    embedded_chunks = embeddings.embed_documents(chunks)
    
    # Prepare data for ChromaDB
    doc_uid = uuid4().hex
    ids = [f"doc_{person_id}_{doc_uid}_{i}" for i in range(len(chunks))]
    metadatas = [
        {"person_id": person_id, "chunk_index": i, "document_name": document_name}
        for i in range(len(chunks))
    ]
    
    # Add to collection
    collection.add(
        embeddings=embedded_chunks,
        documents=chunks,
        metadatas=metadatas,
        ids=ids
    )
    
    return len(chunks)


def search_documents(query: str, top_k: int = 3) -> Dict:
    """Search for relevant documents using similarity search"""
    if not embeddings:
        raise ValueError("OpenAI API key not configured")
    
    # Embed the query
    query_embedding = embeddings.embed_query(query)
    
    # Search in ChromaDB
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )
    
    # Extract results
    documents = results["documents"][0] if results["documents"] else []
    metadatas = results["metadatas"][0] if results["metadatas"] else []
    
    return {
        "documents": documents,
        "metadatas": metadatas
    }


def generate_answer(query: str, context_docs: List[str], language: str = "en") -> str:
    """Generate answer using LLM based on retrieved context"""
    if not llm:
        raise ValueError("OpenAI API key not configured")
    
    # Build context
    context = "\n\n".join([f"Document {i+1}: {doc}" for i, doc in enumerate(context_docs)])
    
    # System prompt with language instruction
    system_prompt = (
        "You are a helpful assistant. Answer the question using ONLY the provided context. "
        "Answer in the exact same language the user asked the question. "
        "If the context doesn't contain the answer, say you don't know."
    )
    
    # User prompt
    user_prompt = f"Context:\n{context}\n\nQuestion: {query}"
    
    # Generate response
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]
    
    response = llm.invoke(messages)
    
    return response.content
