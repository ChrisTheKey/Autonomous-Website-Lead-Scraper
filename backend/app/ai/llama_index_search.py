"""
LlamaIndex-powered semantic search over scraped lead documents.
Indexes raw HTML/text and allows natural-language retrieval.
"""

from llama_index.core import Document, Settings, VectorStoreIndex
from llama_index.llms.openai import OpenAI

from app.core.config import settings

Settings.llm = OpenAI(model=settings.openai_model, api_key=settings.openai_api_key)

_index: VectorStoreIndex | None = None


def build_index(documents: list[dict]) -> VectorStoreIndex:
    global _index
    docs = [
        Document(text=d.get("text", ""), metadata={"url": d.get("url", ""), "company": d.get("company", "")})
        for d in documents
    ]
    _index = VectorStoreIndex.from_documents(docs)
    return _index


def get_index() -> VectorStoreIndex | None:
    return _index


async def search_leads(query: str, top_k: int = 5) -> list[dict]:
    if _index is None:
        return []
    engine = _index.as_query_engine(similarity_top_k=top_k)
    response = await engine.aquery(query)
    results = []
    for node in response.source_nodes:
        results.append(
            {
                "score": round(node.score or 0, 4),
                "url": node.metadata.get("url"),
                "company": node.metadata.get("company"),
                "excerpt": node.text[:300],
            }
        )
    return results
