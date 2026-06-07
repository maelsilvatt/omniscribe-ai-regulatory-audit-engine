import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

import fitz

from src.agents.state import AuditState


def _extract_text_from_pdf(pdf_path: str) -> Tuple[str, int]:
    """
    Synchronous internal function dedicated to PDF text extraction.
    Designed to be executed in a background thread pool to prevent blocking the main asyncio event loop.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Contract file not found at path: {pdf_path}")

    extracted_pages = []
    with fitz.open(pdf_path) as doc:
        total_pages = len(doc)
        for page in doc:
            extracted_pages.append(page.get_text())

    extracted_text = "\n".join(extracted_pages).strip()

    if not extracted_text:
        raise ValueError(
            f"The document '{pdf_path}' is illegible. Verify if it has a text layer or requires OCR."
        )

    return extracted_text, total_pages


async def ingestion_agent_node(state: AuditState) -> Dict[str, Any]:
    """
    Ingestion Agent Node (LangGraph).
    Captures the document path from the state, performs non-blocking asynchronous text extraction,
    and feeds the result to the subsequent agents in the pipeline.
    """
    doc_id = state.get("document_id", "UNKNOWN_DOC")
    doc_url = state.get("document_url", "")

    start_timestamp = datetime.now(timezone.utc).isoformat()

    start_log = [
        {
            "timestamp": start_timestamp,
            "agent": "IngestionAgent",
            "status": "PROCESSING",
            "message": f"Initiating textual extraction pipeline for contract: {doc_id}.",
        }
    ]

    try:
        if not doc_url:
            raise ValueError(
                "The 'document_url' key is missing or empty in the initial graph state."
            )

        # Offload the heavy CPU/IO bound extraction task to a background thread
        document_text, page_count = await asyncio.to_thread(
            _extract_text_from_pdf, doc_url
        )

        end_timestamp = datetime.now(timezone.utc).isoformat()

        end_log = [
            {
                "timestamp": end_timestamp,
                "agent": "IngestionAgent",
                "status": "DONE",
                "message": f"Textual extraction completed. {page_count} page(s) processed and sent for analysis.",
            }
        ]

        # Mutate the global LangGraph state
        return {
            "document_text": document_text,
            "logs": start_log + end_log,
        }

    except Exception as e:
        # Halt the pipeline securely. The orchestrator/websocket layer should catch
        # this exception to notify the client of the critical failure.
        raise RuntimeError(f"Execution failure in IngestionAgent node: {str(e)}") from e
