import os
from typing import List

from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from pydantic import SecretStr

load_dotenv()


class GeminiEmbeddingEngine:
    # Chosen for its strong multilingual performance and semantic density capabilities
    DEFAULT_MODEL = "models/text-embedding-004"

    def __init__(self) -> None:
        api_key = os.getenv("GEMINI_API_KEY")

        # Eager validation: Forces the application to crash immediately on boot
        # if credentials are missing, preventing silent or delayed pipeline failures.
        if not api_key:
            raise ValueError(
                "CRITICAL: The GEMINI_API_KEY environment variable is not configured."
            )

        self.encoder = GoogleGenerativeAIEmbeddings(
            model=self.DEFAULT_MODEL,
            api_key=SecretStr(api_key),
        )

    async def embed_query_async(self, text: str) -> List[float]:
        """
        Generates an embedding vector for a single string.
        Used primarily when an Agent translates a natural language query into a vector for semantic similarity searches.
        """
        return await self.encoder.aembed_query(text)

    async def embed_documents_async(self, texts: List[str]) -> List[List[float]]:
        """
        Generates a list of vectors for multiple text blocks.
        Essential during the ingestion phase for batch-processing document chunks into the vector space.
        """
        return await self.encoder.aembed_documents(texts)
