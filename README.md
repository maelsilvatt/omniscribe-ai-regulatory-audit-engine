# OmniScribe AI — Autonomous Regulatory Due Diligence & Audit Platform

![Architecture](https://img.shields.io/badge/Architecture-Event--Driven_Multi--Agent-blue?style=for-the-badge)
![Inference](https://img.shields.io/badge/Inference-Local_LLM_(Llama_3.1)-orange?style=for-the-badge)
![Vector_DB](https://img.shields.io/badge/Vector_DB-ChromaDB-purple?style=for-the-badge)
![Frontend](https://img.shields.io/badge/Frontend-React_%7C_Next.js-emerald?style=for-the-badge)

OmniScribe AI is an autonomous multi-agent platform engineered to automate complex corporate compliance, legal due diligence, and regulatory auditing workflows. By merging high-performance asynchronous retrieval architectures with state-machine-controlled multi-agent orchestration, OmniScribe AI ingests raw corporate documentation, validates it against volatile regulatory frameworks, and yields deterministic, schema-enforced risk assessment reports.

Built from the ground up to unify low-latency semantic document grounding with bounded agentic workflows, the system forcus on safety, output determinism, and absolute data privacy via local network inference.

---

## 🖥️ System Interface & Compliance Workflows

The OmniScribe AI React frontend provides a streamlined, enterprise-grade workspace for legal and compliance teams to manage legal documents, configure policy weights, and review deterministic audit reports.

### 1. Compliance Workspace & Document Repository
The centralized main hub allows auditors to track global contract ingestion history, review pre-indexed regulatory frameworks (LGPD, ISOs, BACEN), and monitor system-wide compliance health scores.

<p align="center">
  <img src="./images/omniscribe-audit-main-page.png" width="850" alt="OmniScribe AI Main Workspace">
</p>

### 2. Multi-Agent Analysis & Risk Synthesis
When initiating a new compliance scan, the platform enables granular, execution-time configuration. Auditors can drag-and-drop complex multi-page PDF contracts, select specific target regulations, and scale the strictness thresholds.
Once ingested, the document flows into a secondary evaluation state. The `Omniscribe Multi-agent AI` engine coordinates context retrieval from ChromaDB, displays semantic mismatch logs, and streams context-aware risk synthesis into the dashboard.

<p align="center">
  <img src="./images/omniscribe-audit-dashboard-1.png" width="850" alt="Audit Parameters Configuration">
</p>
<p align="center">
  <img src="./images/omniscribe-audit-dashboard-2.png" width="850" alt="Multi-Agent Analysis View">
</p>

---

## 🏛️ System Architecture

OmniScribe AI utilizes an event-driven, fully asynchronous architecture. Multi-agent tasks flow through an explicit state machine, preventing context drift and ensuring strict evaluation loops.

```mermaid
graph TB
    %% Clients and Gateway
    Client([Next.js Frontend]) -->|WebSocket / HTTP| Gateway[FastAPI Gateway]

    %% Orchestrator Core
    subgraph Core [Orchestration Engine]
        Gateway <-->|Async Event Loop| Orchestrator[LangChain State Machine]
        Orchestrator --- State[(Turso DB / libSQL)]
    end

    %% Multi-Agent System
    subgraph SystemAgents [Specialized Autonomous Workers]
        Orchestrator --> IngestionAgent[Ingestion Agent]
        Orchestrator --> SearchAgent[Semantic Search Agent]
        Orchestrator --> AuditorAgent[Auditor Agent]
        Orchestrator --> GovAgent[Governance Agent]
    end

    %% Knowledge Base & LLM Engine
    subgraph Knowledge [Asynchronous RAG Layer]
        SearchAgent <-->|Vector Search| VectorDB[(ChromaDB Vector Store)]
        DocPipeline[Async Chunking Pipeline] --> VectorDB
    end

    subgraph ModelEngines [Inference & Embeddings]
        IngestionAgent <--> Ollama[Ollama - Llama 3.1]
        AuditorAgent <--> Ollama
        GovAgent <--> Ollama
        SearchAgent <--> Gemini[Gemini - Embeddings]
        DocPipeline <--> Gemini
    end

    %% Validation Layer
    subgraph Validation [Compliance & Structuring]
        GovAgent --> Schema[Pydantic Schema Validation]
        Schema -->|Deterministic JSON| Gateway
    end

    %% Styling
    style Client fill:#edf2f7,stroke:#4a5568,stroke-width:2px
    style Gateway fill:#ebf8ff,stroke:#2b6cb0,stroke-width:2px
    style Orchestrator fill:#f0fff4,stroke:#2f855a,stroke-width:2px
    style State fill:#e6ffed,stroke:#2ea043,stroke-width:2px
    style VectorDB fill:#fff5f5,stroke:#9b2c2c,stroke-width:2px
    style Ollama fill:#e1f5fe,stroke:#0288d1,stroke-width:2px
    style Gemini fill:#fefcbf,stroke:#975a16,stroke-width:2px
    style Schema fill:#faf5ff,stroke:#553c9a,stroke-width:2px

```
### Multi-Agent Workflow

The system relies on a specialized multi-agent pipeline orchestrated by a LangGraph state machine. Each agent has a strictly bounded context and deterministic role:

```mermaid
graph TD
    Orchestrator[LangGraph Orchestrator]
    
    subgraph Autonomous Agent Pipeline
        direction TB
        Ingestion[1. Ingestion Agent]
        Search[2. Semantic Search Agent]
        Auditor[3. Auditor Agent]
        Governance[4. Governance Agent]
    end
    
    Orchestrator -->|Triggers Pipeline| Ingestion
    Ingestion -->|Extracts & Chunks Text| Search
    Search -->|Retrieves Legal Context| Auditor
    Auditor -->|Synthesizes Risk| Governance
    Governance -->|Validates JSON Schema| Orchestrator
    
    classDef agent fill:#e1f5fe,stroke:#0288d1,stroke-width:2px,color:#000;
    classDef orch fill:#f0fff4,stroke:#2f855a,stroke-width:2px,color:#000;
    class Ingestion,Search,Auditor,Governance agent;
    class Orchestrator orch;
```
* **Ingestion Agent:** Responsible for parsing raw multi-page PDF contracts, and chunking the text into semantic blocks optimized for the LLM's context window.
* **Semantic Search Agent:** Acts as the RAG engineer. It takes the contract chunks, formulates optimized queries, and searches the ChromaDB vector store (powered by Google Gemini embeddings) to fetch the exact regulatory clauses needed for the audit.
* **Auditor Agent:** The core analytical brain (powered by local Llama 3.1). It cross-references the ingested contract clauses against the retrieved legal context to identify vulnerabilities, non-compliance issues, and liability risks.
* **Governance Agent:** It evaluates the Auditor's raw text output and forces it into a strict Pydantic schema, ensuring the frontend receives perfectly formatted, deterministic JSON objects without hallucinations.

## ✨ Key Features

* **Data Privacy First (Local Inference):** Auditing agents run on local LLMs (Ollama + Llama 3.1), ensuring highly sensitive corporate contracts never leave the internal network during the critical analysis phase.
* **Agentic RAG Flow:** Embedded autonomous query optimization and recursive retrieval. The *Search Agent* localizes comprehensive regulatory backing data using Google Gemini's advanced text-embedding models.
* **State-Machine Multi-Agent Coordination:** Eliminates chain-of-thought hallucination and non-deterministic agent loops by enforcing rigorous DAG (Directed Acyclic Graph) state boundaries via LangGraph, persisted securely in the cloud via Turso DB.
* **Real-Time Asynchronous Streaming:** Utilizing FastAPI and Python's native `asyncio`, the platform streams active agent steps, inner thoughts, and incremental auditing logs straight to the React frontend over WebSockets.
* **Strict Structural Enforcement:** Eliminates text-parsing post-processing vulnerabilities. By leveraging structured outputs mapped directly into complex `Pydantic` schemas, the final audit delivery is mathematically guaranteed to align with the frontend JSON structures.

---

## 📂 Project Structure

```text
omniscribe-ai/
├── docker-compose.yml
├── .env
├── README.md
├── frontend/                   # Next.js Application
│   ├── src/
│   │   ├── app/                # React Server Components & Routing
│   │   └── components/         # UI Elements & Dashboards
│   ├── Dockerfile
│   └── package.json
└── backend/                    # FastAPI Application
    ├── Dockerfile
    ├── requirements.txt
    ├── src/
    │   ├── main.py             # FastAPI Entrypoint & WebSocket Routers
    │   ├── agents/             # Multi-Agent Orchestration Core
    │   │   ├── graph.py        # LangChain State Machine Graph Definition
    │   │   ├── state.py        # State Schema Definition
    │   │   └── workers/        # Specialized Agent Nodes (Ingestion, Auditor, etc.)
    │   ├── database/           # Persistence Layer
    │   │   └── turso_saver.py  # Custom LangGraph libSQL Checkpointer
    │   ├── rag/                # Retrieval-Augmented Generation Engine
    │   │   ├── chroma_client.py
    │   │   ├── embeddings.py
    │   │   └── pipeline.py
    │   └── schemas/            # Strict Pydantic Contracts
    └── tests/                  # Pytest Suite

```

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
| --- | --- | --- |
| **Frontend** | Next.js (React), Tailwind CSS | Client interface and real-time WebSocket dashboard |
| **Backend API** | FastAPI, Uvicorn, Asyncio | High-performance asynchronous event-driven server |
| **Orchestration** | LangGraph, LangChain | State machine coordination for multi-agent workflows |
| **Inference (LLM)** | Ollama (Llama 3.1) | Local, privacy-preserving analytical reasoning |
| **Embeddings** | Google Gemini (`text-embedding-004`) | Multilingual semantic vector representation |
| **Vector Database** | ChromaDB | Semantic document storage and context retrieval |
| **State DB** | Turso (libSQL) | Distributed, low-latency checkpointing and audit history |
| **Validation** | Pydantic v2 | Deterministic schema enforcement and strict typing |

---

## 🚀 Getting Started

### Prerequisites

* Docker and Docker Compose
* Google AI Studio Account (Gemini API Key)
* Turso DB Account (Database URL & Auth Token)
* Ollama installed locally (if not running containerized GPU environments)

### Environment Configuration

Create a `.env` file in the root directory:

| Variable | Description | Example |
| --- | --- | --- |
| `GEMINI_API_KEY` | Google API key for embedding generation | `AIzaSy...` |
| `TURSO_DATABASE_URL` | Local libSQL database connection string | `libsql://your-db.turso.io` |
| `TURSO_AUTH_TOKEN` | Authentication token for Turso DB | `ey...` |
| `OLLAMA_BASE_URL` | Endpoint for the local Ollama instance | `http://host.docker.internal:11434` |
| `VECTOR_COLLECTION_NAME` | ChromaDB internal collection name | `omniscribe_vault` |

### Deployment (Docker Compose)

The easiest way to run the entire OmniScribe AI ecosystem is via Docker Compose, which seamlessly builds and links the frontend and backend networks.

1. Clone the repository and configure your `.env` file.
2. Start the local Ollama service and pull the required model:

```bash
ollama serve
ollama pull llama3.1

```

3. Boot the application cluster:

```bash
docker-compose up --build

```

* **Frontend Dashboard**: `http://localhost:3000`
* **Backend API Docs**: `http://localhost:8000/docs`

---

## 🧪 Example API Usage

### Initiate an Audit Session

Submit corporate documents for execution against specific regulatory guidelines via a `multipart/form-data` request.

**Endpoint:** `POST /api/v1/audit/initiate`

**cURL Example:**

```bash
curl -X POST "http://localhost:8000/api/v1/audit/initiate" \
  -F "document_id=VENDOR_AGREEMENT_2026" \
  -F "regulatory_frameworks=LGPD" \
  -F "strictness_level=high" \
  -F "file=@/path/to/contract.pdf"

```

**JSON Response:**

```json
{
  "session_id": "8b9a3f2c",
  "status": "QUEUED",
  "websocket_stream_url": "/api/v1/audit/stream/8b9a3f2c"
}

```

### Real-Time Event Streaming

Connecting to the provided WebSocket URL emits standard JSON event packets detailing execution milestones:

```json
{
  "event": "agent_execution_step",
  "agent": "AuditorAgent",
  "status": "PROCESSING",
  "message": "Cross-referencing contractual clauses with local laws via local LLM.",
  "timestamp": "2026-06-07T04:57:00Z"
}

```

---

## 📚 References & Documentation

For more detailed information regarding the core technologies and engines used in this project, please refer to their official documentation:

* **[LangGraph / LangChain](https://www.google.com/search?q=https://python.langchain.com/v0.1/docs/langgraph/)** - State machine orchestration for multi-agent workflows.
* **[Ollama](https://ollama.com/)** - Local LLM execution and inference.
* **[ChromaDB](https://www.trychroma.com/)** - Open-source embedding database.
* **[Turso](https://turso.tech/)** - Edge-hosted SQLite database (libSQL).
* **[FastAPI](https://fastapi.tiangolo.com/)** - High-performance Python web framework.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](https://www.google.com/search?q=LICENSE) file for details.