import uuid
from typing import Any, Dict, List

from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.rag.chroma_client import ChromaManager
from src.rag.embeddings import GeminiEmbeddingEngine


class RegulatoryIngestionPipeline:
    def __init__(self) -> None:
        self.chroma_manager = ChromaManager()
        self.embedding_engine = GeminiEmbeddingEngine()

        # Text Splitter Configuration:
        # Optimized for legal and regulatory documents. The overlap ensures that sentences
        # split across boundaries don't lose their legal context.
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=[
                "\n\n",  # First priority: Paragraph breaks
                "\n",  # Second priority: Line breaks
                " ",  # Third priority: Word breaks
                "",  # Fallback: Character level
            ],
        )

    def _generate_chunk_id(self, framework_name: str) -> str:
        """Generates a predictable, unique identifier for a vector chunk."""
        return f"chk_{framework_name.lower()}_{uuid.uuid4().hex[:8]}"

    def _build_metadata(
        self, framework_name: str, index: int, total_chunks: int
    ) -> Dict[str, Any]:
        """Builds structured metadata, allowing specific pre-filtering during vector searches."""
        return {
            "framework": framework_name.upper(),
            "chunk_index": index,
            "total_chunks": total_chunks,
            "source": f"Internal Regulatory Injection — {framework_name.upper()}",
        }

    async def run_ingestion_async(
        self, raw_text: str, framework_name: str
    ) -> Dict[str, Any]:
        """
        Processes raw regulatory text, splits it into chunks,
        and stores it asynchronously in the ChromaDB vector database.
        """
        # 1. Split the massive raw text into digestible semantic chunks
        chunks = self.text_splitter.split_text(raw_text)

        if not chunks:
            return {
                "status": "skipped",
                "reason": "Empty text or no content to process.",
            }

        prepared_documents: List[str] = []
        prepared_metadatas: List[Dict[str, Any]] = []
        prepared_ids: List[str] = []

        total_chunks = len(chunks)

        # 2. Prepare structured data and metadata arrays
        for index, chunk in enumerate(chunks):
            prepared_documents.append(chunk)
            prepared_ids.append(self._generate_chunk_id(framework_name))
            prepared_metadatas.append(
                self._build_metadata(framework_name, index, total_chunks)
            )

        # 3. Asynchronously persist into the vector database
        await self.chroma_manager.add_documents_async(
            documents=prepared_documents,
            metadatas=prepared_metadatas,
            ids=prepared_ids,
        )

        return {
            "status": "success",
            "framework": framework_name.upper(),
            "chunks_processed": total_chunks,
        }
