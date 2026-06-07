from typing import Annotated, Any, Dict, List, Optional, TypedDict

from src.schemas.audit import FinalAuditReport


def append_log(
    left: List[Dict[str, Any]], right: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Reducer function for the 'logs' key in the LangGraph state.
    Ensures that execution logs are appended sequentially across different nodes,
    enabling real-time streaming via WebSockets without losing historical steps.
    """
    return left + right


class AuditState(TypedDict):
    """
    The central state structure managed by the LangGraph checkpointer.
    Data flows sequentially from top to bottom as each specialized agent mutates the state.
    """

    # --- INPUT DATA (Injected at the START node) ---
    document_id: str
    document_url: str
    regulatory_frameworks: List[str]
    strictness_level: str

    # --- INTERMEDIATE MEMORY (Populated progressively by workers) ---

    # Mutated by: IngestionAgent
    document_text: Optional[str]

    # Mutated by: SearchAgent (Relevant articles extracted from ChromaDB)
    retrieved_contexts: Optional[List[Dict[str, Any]]]

    # Mutated by: AuditorAgent (Draft analysis and found non-conformities)
    raw_analysis: Optional[str]

    # --- FINAL OUTPUT (Validated and structured by GovernanceAgent) ---
    # The Pydantic contract that will be returned to the API layer
    final_report: Optional[FinalAuditReport]

    # --- EVENT HISTORY (Real-time telemetry) ---
    # Agents append structured dictionaries: {"agent": str, "status": str, "message": str, "timestamp": str}
    logs: Annotated[List[Dict[str, Any]], append_log]
