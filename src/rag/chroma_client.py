import asyncio
import os
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings
from dotenv import load_dotenv

load_dotenv()


class ChromaManager:
    def __init__(self) -> None:
        self.collection_name = os.getenv(
            "VECTOR_COLLECTION_NAME", "omniscribe_regulatory_vault"
        )

        # Local persistent directory for development.
        # In production, this should point to a remote ChromaDB server/container via chromadb.HttpClient().
        self.client = chromadb.PersistentClient(
            path="./chroma_data", settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self._get_or_create_collection()

    def _get_or_create_collection(self) -> chromadb.Collection:
        """
        Initializes or retrieves the default document collection.
        Configures the vector space to use Cosine distance, which is mathematically optimal for text/semantic embeddings.
        """
        return self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def _sync_add_documents(
        self, documents: List[str], metadatas: List[Dict[str, Any]], ids: List[str]
    ) -> None:
        """Internal synchronous wrapper to insert documents."""
        self.collection.add(documents=documents, metadatas=metadatas, ids=ids)

    def _sync_query_collection(
        self,
        query_text: str,
        n_results: int = 3,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Internal synchronous wrapper to query the vector collection."""
        return self.collection.query(
            query_texts=[query_text], n_results=n_results, where=where
        )

    # --- PUBLIC ASYNCHRONOUS INTERFACE ---

    async def add_documents_async(
        self, documents: List[str], metadatas: List[Dict[str, Any]], ids: List[str]
    ) -> None:
        """
        Asynchronously inserts raw documents and metadata into ChromaDB.
        Delegates the blocking database I/O to a background thread to keep the FastAPI event loop responsive.
        """
        await asyncio.to_thread(self._sync_add_documents, documents, metadatas, ids)

    async def query_semantic_context_async(
        self,
        query_text: str,
        n_results: int = 3,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Performs an asynchronous semantic search.
        Flattens and normalizes ChromaDB's nested list response into a clean list of dictionaries for easier Agent consumption.
        """
        raw_results = await asyncio.to_thread(
            self._sync_query_collection, query_text, n_results, where
        )

        formatted_results = []

        # Validate that the response contains populated arrays
        if (
            not raw_results
            or not raw_results.get("documents")
            or not raw_results["documents"][0]
        ):
            return formatted_results

        # Extract the first inner list (since we only submitted a single query_text)
        documents = raw_results["documents"][0]
        metadatas = raw_results["metadatas"][0]
        ids = raw_results["ids"][0]

        # Depending on query config, 'distances' might be omitted. Safe fallback applied.
        distances_raw = raw_results.get("distances")
        distances = (
            distances_raw[0]
            if distances_raw and distances_raw[0]
            else [None] * len(documents)
        )

        # Zip cleanly groups the unnested arrays by index
        for doc_id, content, meta, dist in zip(ids, documents, metadatas, distances):
            # Convert Cosine distance to a Similarity Score where closer to 1.0 is better
            score = 1.0 - dist if dist is not None else None

            formatted_results.append(
                {
                    "id": doc_id,
                    "content": content,
                    "metadata": meta,
                    "score": score,
                }
            )

        return formatted_results
