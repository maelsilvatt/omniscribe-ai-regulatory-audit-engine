import asyncio
from datetime import datetime, timezone
from typing import Any, Dict

from src.agents.state import AuditState
from src.rag.chroma_client import ChromaManager


async def search_agent_node(state: AuditState) -> Dict[str, Any]:
    """
    Semantic Search Agent Node.
    Identifies the target regulatory frameworks and performs filtered, asynchronous
    searches in the vector database to gather contextual evidence for the audit.
    """
    frameworks = state.get("regulatory_frameworks", [])

    start_timestamp = datetime.now(timezone.utc).isoformat()
    start_log = [
        {
            "timestamp": start_timestamp,
            "agent": "SearchAgent",
            "status": "PROCESSING",
            "message": f"Initiating semantic scan for the following frameworks: {frameworks}.",
        }
    ]

    # UX Pacing: Artificial delay to ensure the frontend WebSocket stream has time to
    # render the state transition smoothly without visual flickering.
    await asyncio.sleep(1.5)

    chroma_manager = ChromaManager()

    # Design Decision: Encapsulating the search logic into an async helper allows
    # for concurrent execution via asyncio.gather, eliminating sequential bottlenecks.
    async def _fetch_framework_context(framework: str) -> list:
        search_query = (
            f"Personal data processing, data retention, security incidents, "
            f"and penalties under {framework}"
        )
        return await chroma_manager.query_semantic_context_async(
            query_text=search_query,
            n_results=3,
            where={"framework": framework},
        )

    # Dispatch all vector database searches concurrently
    search_tasks = [_fetch_framework_context(fw) for fw in frameworks]
    results_matrix = await asyncio.gather(*search_tasks)

    # Flatten the matrix (list of lists) into a single continuous list of contexts
    retrieved_contexts = [context for sublist in results_matrix for context in sublist]

    end_timestamp = datetime.now(timezone.utc).isoformat()
    end_log = [
        {
            "timestamp": end_timestamp,
            "agent": "SearchAgent",
            "status": "DONE",
            "message": f"Search completed. {len(retrieved_contexts)} regulatory references mapped and attached to context.",
        }
    ]

    return {
        "retrieved_contexts": retrieved_contexts,
        "logs": start_log + end_log,
    }
