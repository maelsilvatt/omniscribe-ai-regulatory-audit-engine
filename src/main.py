import asyncio
import os
import shutil
import subprocess
import traceback
import uuid
from contextlib import asynccontextmanager
from typing import Dict, Any, List

import httpx
from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import custom Turso checkpointer
from src.database.turso_saver import TursoCheckpointSaver

# Import structured workflow
from src.agents.graph import audit_workflow
from src.schemas.audit import FinalAuditReport

load_dotenv()

# Environment Configurations
TURSO_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_VERSION_URL = f"{OLLAMA_BASE_URL}/api/version"

# In-memory store for active sessions. In a production distributed environment, consider using Redis.
ACTIVE_SESSIONS: Dict[str, Dict[str, Any]] = {}


async def ensure_ollama_is_running() -> bool:
    """
    Verifies if Ollama is running locally.
    If offline, attempts to initialize the service automatically in the background,
    ensuring full access to the CUDA/GPU driver on Windows.
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(OLLAMA_VERSION_URL, timeout=2.0)
            if response.status_code == 200:
                print("🟢 [OMNISCRIBE ENGINE] Ollama detected and operating normally.")
                return True
        except httpx.RequestError:
            print("⚠️ [OMNISCRIBE ENGINE] Ollama not detected on port 11434.")
            print(
                "🚀 Attempting to initialize the 'ollama serve' service automatically..."
            )

        # Locate the Ollama binary
        ollama_bin = shutil.which("ollama")
        if not ollama_bin:
            if os.name == "nt":
                user_profile = os.environ.get("USERPROFILE", "C:\\Users\\default")
                default_path = os.path.join(
                    user_profile, "AppData", "Local", "Programs", "Ollama", "ollama.exe"
                )
                ollama_bin = default_path if os.path.exists(default_path) else "ollama"

        try:
            # FOR WINDOWS CUDA:
            # We configure the DETACHED_PROCESS flag. This unbinds Ollama from the Uvicorn
            # terminal restrictions, allowing it to natively access the video hardware.
            creation_flags = subprocess.DETACHED_PROCESS if os.name == "nt" else 0

            subprocess.Popen(
                [ollama_bin, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=os.environ.copy(),
                shell=False,
                creationflags=creation_flags,
            )

            max_attempts = 10
            print(
                f"⏳ Service triggered via '{ollama_bin}'. Waiting for port stabilization (max {max_attempts}s)..."
            )

            for attempt in range(1, max_attempts + 1):
                await asyncio.sleep(1)
                try:
                    response = await client.get(OLLAMA_VERSION_URL, timeout=1.0)
                    if response.status_code == 200:
                        print(
                            f"🟢 [OMNISCRIBE ENGINE] Ollama woke up and responded successfully on attempt {attempt}!"
                        )
                        return True
                except httpx.RequestError:
                    print(
                        f"   [{attempt}/{max_attempts}] Port spinning up or unstable, waiting..."
                    )
                    continue

            print(
                "❌ [ERROR] The process was called, but the Ollama API did not stabilize in time."
            )
            return False

        except Exception as e:
            print(
                f"❌ [CRITICAL ERROR] Failed to automatically start Ollama. Details: {repr(e)}"
            )
            return False


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """
    Manages safe initialization: checks AI dependencies (Ollama)
    and opens the connection pool with the cloud Turso DB.
    """
    await ensure_ollama_is_running()

    async with TursoCheckpointSaver(TURSO_URL, TURSO_TOKEN) as checkpointer:
        app.state.audit_graph = audit_workflow.compile(checkpointer=checkpointer)
        app.state.checkpointer = checkpointer
        yield


app = FastAPI(
    title="OmniScribe AI — Autonomous Regulatory Audit API",
    description="Event-driven asynchronous API for compliance auditing via multi-agents.",
    version="1.0.0",
    lifespan=app_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuditResponse(BaseModel):
    session_id: str
    status: str
    websocket_stream_url: str


@app.get("/", tags=["Health Check"])
def read_root() -> Dict[str, str]:
    return {"status": "healthy", "service": "OmniScribe AI API"}


def _normalize_report(report: Any) -> dict:
    """Helper to convert Pydantic models or objects to a standard dictionary."""
    if isinstance(report, dict):
        return report
    if hasattr(report, "model_dump"):
        return report.model_dump()
    return {}


# --- HISTORICAL QUERY VIA TURSO/LANGGRAPH (UNIFIED AND ASYNCHRONOUS) ---
@app.get(
    "/api/v1/audit/report/{session_id}", response_model=dict, tags=["Audit Summary"]
)
async def get_historical_report(session_id: str, request: Request) -> dict:
    """Fetches the final snapshot of a completed audit directly from the Turso DB."""
    graph_config = {"configurable": {"thread_id": f"th_{session_id}"}}

    try:
        audit_engine = request.app.state.audit_graph
        state_snapshot = await audit_engine.aget_state(config=graph_config)

        if not state_snapshot or not state_snapshot.values:
            raise HTTPException(
                status_code=404,
                detail=f"Report for session '{session_id}' was not found in the history.",
            )

        final_report = state_snapshot.values.get("final_report")

        if not final_report:
            raise HTTPException(
                status_code=202,
                detail="The audit has started, but the final report has not yet been generated by the GovernanceAgent.",
            )

        return _normalize_report(final_report)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal error reading history from Turso DB: {str(e)}",
        )


# --- LIST ALL AUDIT HISTORY (OPTIMIZED FOR TURSO) ---
@app.get("/api/v1/audit/history", tags=["Audit Summary"])
async def list_audit_history(request: Request) -> List[Dict[str, Any]]:
    """
    Scans the Turso database, identifies all unique finalized sessions,
    and returns the formatted list to populate the frontend table.
    """
    audit_engine = request.app.state.audit_graph
    checkpointer = request.app.state.checkpointer
    history_list = []

    try:
        # Fetches the latest checkpoint of each thread directly from the Turso cloud
        res = await checkpointer.client.execute("""
            SELECT thread_id, MAX(checkpoint_id) as latest_check 
            FROM checkpoints 
            GROUP BY thread_id
        """)

        thread_ids = [row[0] for row in res.rows]
        if not thread_ids:
            return []

        # Pull saved states for the found threads
        for t_id in thread_ids:
            session_id = t_id.replace("th_", "")
            graph_config = {"configurable": {"thread_id": t_id}}

            state_snapshot = await audit_engine.aget_state(config=graph_config)

            if not (state_snapshot and state_snapshot.values):
                continue

            final_report_raw = state_snapshot.values.get("final_report")
            if not final_report_raw:
                continue

            # Normalize data to a dictionary to avoid repetitive hasattr/get calls
            report_data = _normalize_report(final_report_raw)
            summary_data = report_data.get("summary", {})
            frameworks = report_data.get("frameworks_evaluated", [])

            # Ensure the target regulation is a clean string (e.g., "CDC") instead of an array
            frameworks_str = (
                ", ".join(frameworks)
                if isinstance(frameworks, list)
                else str(frameworks)
            )

            history_list.append(
                {
                    "session_id": session_id,
                    "document_id": report_data.get("document_id", "N/A"),
                    "frameworks_evaluated": frameworks_str,
                    "audited_at": report_data.get("audited_at", ""),
                    "compliance_score": summary_data.get("compliance_score", 0),
                    "total_issues": summary_data.get("total_issues", 0),
                }
            )

        # Sort: Newest first
        history_list.sort(key=lambda x: x["audited_at"] or "", reverse=True)
        return history_list

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process history listing from Turso DB: {str(e)}",
        )


@app.post("/api/v1/audit/initiate", response_model=AuditResponse, tags=["Audit"])
async def initiate_audit(
    document_id: str = Form(...),
    regulatory_frameworks: str = Form(...),
    strictness_level: str = Form("high"),
    file: UploadFile = File(...),
) -> AuditResponse:
    session_id = str(uuid.uuid4())[:8]

    # Sanitized filename to prevent path traversal
    safe_filename = os.path.basename(file.filename)
    saved_file_path = f"./{safe_filename}"

    try:
        with open(saved_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Critical I/O failure while writing file to local server: {str(e)}",
        )

    ACTIVE_SESSIONS[session_id] = {
        "document_id": document_id,
        "document_url": saved_file_path,
        "regulatory_frameworks": [regulatory_frameworks.strip().upper()],
        "strictness_level": strictness_level,
    }

    return AuditResponse(
        session_id=session_id,
        status="QUEUED",
        websocket_stream_url=f"/api/v1/audit/stream/{session_id}",
    )


@app.websocket("/api/v1/audit/stream/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()

    session_data = ACTIVE_SESSIONS.get(session_id)
    if not session_data:
        await websocket.send_json(
            {"event": "error", "message": "Session expired or not found."}
        )
        await websocket.close()
        return

    try:
        await websocket.send_json(
            {
                "event": "session_connected",
                "session_id": session_id,
                "message": "Connection established. Preparing inference engines...",
            }
        )

        graph_config = {"configurable": {"thread_id": f"th_{session_id}"}}
        initial_state = {
            "document_id": session_data["document_id"],
            "document_url": session_data["document_url"],
            "regulatory_frameworks": session_data["regulatory_frameworks"],
            "strictness_level": session_data["strictness_level"],
            "logs": [],
        }

        audit_engine = websocket.app.state.audit_graph

        async for event in audit_engine.astream(initial_state, config=graph_config):
            for node_name, node_output in event.items():

                # Stream logs back to the client if available
                if node_output.get("logs"):
                    latest_log = node_output["logs"][-1]
                    await websocket.send_json(
                        {
                            "event": "agent_execution_step",
                            "agent": latest_log.get("agent"),
                            "status": latest_log.get("status"),
                            "message": latest_log.get("message"),
                            "timestamp": latest_log.get("timestamp"),
                        }
                    )

                # Once the governance agent finishes, emit the final payload
                if node_name == "governance_agent" and "final_report" in node_output:
                    payload_data = _normalize_report(node_output["final_report"])
                    await websocket.send_json(
                        {
                            "event": "audit_completed",
                            "session_id": session_id,
                            "payload": payload_data,
                        }
                    )

    except WebSocketDisconnect:
        print(f"Client disconnected from WebSocket session: {session_id}")
    except Exception as e:
        print("\n💥 [CRASH DETECTED IN AGENT FLOW] 💥")
        traceback.print_exc()
        print("-" * 41 + "\n")

        # Catch-all to gracefully inform the client of an internal crash before closing
        try:
            await websocket.send_json(
                {
                    "event": "error",
                    "message": f"Internal failure in the agent engine: {repr(e)}",
                }
            )
        except RuntimeError:
            pass  # Socket already closed
    finally:
        # Cleanup the temporary session state
        ACTIVE_SESSIONS.pop(session_id, None)
        try:
            await websocket.close()
        except RuntimeError:
            pass  # Socket already closed
