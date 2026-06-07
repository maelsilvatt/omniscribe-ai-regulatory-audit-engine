from datetime import datetime, timezone
from typing import Any, Dict

from src.agents.state import AuditState
from src.config.llm import get_llm
from src.schemas.audit import FinalAuditReport


async def governance_agent_node(state: AuditState) -> Dict[str, Any]:
    """
    Governance Agent Node.
    Uses the LLM strictly for unstructured data extraction/formatting (via Pydantic),
    then applies pure Python logic to guarantee absolute mathematical precision in the compliance score.
    """
    document_id = state.get("document_id", "UNKNOWN_DOC")
    frameworks = state.get("regulatory_frameworks", [])
    raw_analysis = state.get("raw_analysis", "")

    start_timestamp = datetime.now(timezone.utc).isoformat()
    start_log = [
        {
            "timestamp": start_timestamp,
            "agent": "GovernanceAgent",
            "status": "PROCESSING",
            "message": "Initiating local data structuring with Pydantic Schema Enforcement.",
        }
    ]

    llm = get_llm()
    structured_llm = llm.with_structured_output(FinalAuditReport)

    # System prompt maintained in Portuguese as explicitly requested
    system_prompt = (
        "Você é um engenheiro de dados de compliance e auditor sênior. Sua única tarefa é ler a ANÁLISE BRUTA "
        "fornecida e extrair/formatar todas as informações no formato estruturado exigido.\n\n"
        "Regras Adicionais de Validação:\n"
        f"1. Preencha o 'document_id' estritamente com o valor: {document_id}\n"
        f"2. Preencha os 'frameworks_evaluated' com a lista: {frameworks}\n"
        "3. Mapeie todos os achados encontrados na lista 'findings'.\n"
        "4. GRANULARIDADE MÁXIMA: No campo 'doc_clause_reference', capture a localização mais específica e profunda "
        "indicada na análise (ex: prefira 'Cláusula 2.3' ou 'Cláusula 2, Parágrafo Único' em vez de apenas 'CLÁUSULA 2').\n"
        "5. CRÍTICO (ENUM VALIDATION): O campo 'risk_level' DEVE ser estritamente uma das seguintes strings em inglês: "
        "'LOW', 'MEDIUM', 'HIGH' ou 'CRITICAL'. Mapeie 'Baixo'->'LOW', 'Médio'->'MEDIUM', 'Alto'->'HIGH' e 'Crítico'->'CRITICAL'.\n\n"
        "6. ISOLAMENTO DE REMEDIAÇÃO: Cada achado deve ter uma ação corretiva ('remediation_steps') "
        "estritamente personalizada para a descrição daquele problema específico. "
        "NÃO repita o texto de remediação de um achado em outro achado diferente.\n\n"
        f"=== ANÁLISE BRUTA PARA EXTRAÇÃO ===\n{raw_analysis}"
    )

    # The LLM generates the initial structure, populating the 'findings' list
    final_report: FinalAuditReport = await structured_llm.ainvoke(system_prompt)

    # =========================================================================
    # DETERMINISTIC MATH ENGINE & DATA SANITIZATION (PURE PYTHON)
    # =========================================================================

    # 1. Enforce strict sequential ID standardization (e.g., AUD-001, AUD-002...)
    for idx, finding in enumerate(final_report.findings, start=1):
        finding.id = f"AUD-{idx:03d}"

    # 2. Reset and aggregate risk levels using structural Enum resolution
    risk_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}

    for finding in final_report.findings:
        raw_level = finding.risk_level

        if hasattr(raw_level, "value"):
            normalized_level = str(raw_level.value).upper().strip()
        else:
            normalized_level = str(raw_level).upper().strip()

        if normalized_level in risk_counts:
            risk_counts[normalized_level] += 1

    # 3. Apply exact enterprise penalty architecture rules
    compliance_score = 100.0 - (
        risk_counts["CRITICAL"] * 25.0
        + risk_counts["HIGH"] * 15.0
        + risk_counts["MEDIUM"] * 5.0
        + risk_counts["LOW"] * 2.0
    )

    # Boundary guard: Compliance performance cannot drop below absolute floor
    compliance_score = max(0.0, compliance_score)

    # 4. Bind recalculated mathematical values back into the validation schema container
    final_report.summary.total_issues = len(final_report.findings)
    final_report.summary.critical_risk_count = risk_counts["CRITICAL"]
    final_report.summary.high_risk_count = risk_counts["HIGH"]
    final_report.summary.medium_risk_count = risk_counts["MEDIUM"]
    final_report.summary.low_risk_count = risk_counts["LOW"]
    final_report.summary.compliance_score = compliance_score
    # =========================================================================

    end_timestamp = datetime.now(timezone.utc).isoformat()
    end_log = [
        {
            "timestamp": end_timestamp,
            "agent": "GovernanceAgent",
            "status": "DONE",
            "message": f"Final report structured and validated via Python! Real Compliance Score: {compliance_score}.",
        }
    ]

    return {
        "final_report": final_report.model_dump(),
        "logs": start_log + end_log,
    }
