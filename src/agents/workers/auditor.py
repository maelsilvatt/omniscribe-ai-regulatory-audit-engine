from datetime import datetime, timezone
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.state import AuditState
from src.config.llm import get_llm


async def auditor_agent_node(state: AuditState) -> Dict[str, Any]:
    """
    Executes the Auditor Agent logic using a local LLM via Ollama.
    Responsible for contrasting the user's document against retrieved regulatory contexts.
    """
    document_text = state.get("document_text", "")
    retrieved_contexts = state.get("retrieved_contexts", [])
    strictness_level = state.get("strictness_level", "high")

    start_timestamp = datetime.now(timezone.utc).isoformat()

    start_log = [
        {
            "timestamp": start_timestamp,
            "agent": "AuditorAgent",
            "status": "PROCESSING",
            "message": "Cross-referencing contractual clauses with local laws via local LLM.",
        }
    ]

    # Instantiate the local LLM with an optimized context window constraint
    llm = get_llm(num_predict=1024)

    # Efficiently construct the context payload
    formatted_laws_blocks = [
        f"\n--- Regulatory Reference #{idx+1} (ID: {ctx.get('id', 'N/A')}) ---\nContent: {ctx.get('content', '')}\n"
        for idx, ctx in enumerate(retrieved_contexts)
    ]
    formatted_laws = "".join(formatted_laws_blocks)

    # System prompt maintained in Portuguese as explicitly requested
    system_instruction = (
        "Você é um Auditor de Compliance Jurídico e Regulatório sênior especializado em identificar riscos e infrações. "
        "Sua tarefa é confrontar o texto do CONTRATO fornecido pelo usuário com as REFERÊNCIAS REGULATÓRIAS (leis/normas) "
        "trazidas pelo sistema de busca. Identifique TODAS as cláusulas contratuais que violam ou trazem riscos em relação às normas fornecidas.\n\n"
        f"Nível de Rigor da Auditoria: {strictness_level.upper()}\n"
        "Exigência de Granularidade: Seja extremamente específico ao apontar a localização do erro. "
        "NÃO cite apenas o título principal da cláusula (ex: 'CLÁUSULA 2'). Você deve mapear o subnível exato, "
        "como parágrafos, incisos, itens ou alíneas onde a infração está escrita (ex: 'Cláusula 2.1', 'Cláusula 3, § 2º', 'Cláusula 4, Item b').\n\n"
        "Para cada problema encontrado, você deve extrair textualmente a cláusula infratora, "
        "citar qual artigo/lei foi violado, explicar o motivo e sugerir uma redação corretiva."
    )

    user_content = (
        f"=== REFERÊNCIAS REGULATÓRIAS COMPROVADAS ===\n{formatted_laws}\n\n"
        f"=== TEXTO DO CONTRATO A SER AUDITADO ===\n{document_text}\n\n"
        "Gere um relatório analítico e detalhado contendo todos os achados (findings) de inconformidade."
    )

    messages = [
        SystemMessage(content=system_instruction),
        HumanMessage(content=user_content),
    ]

    # Dispatch the asynchronous inference call
    response = await llm.ainvoke(messages)

    end_timestamp = datetime.now(timezone.utc).isoformat()

    return {
        "raw_analysis": response.content,
        "logs": start_log
        + [
            {
                "timestamp": end_timestamp,
                "agent": "AuditorAgent",
                "status": "DONE",
                "message": "Critical analysis completed successfully by the local model.",
            }
        ],
    }
