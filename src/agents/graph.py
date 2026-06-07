from langgraph.graph import END, START, StateGraph

from src.agents.state import AuditState
from src.agents.workers.auditor import auditor_agent_node
from src.agents.workers.governance import governance_agent_node
from src.agents.workers.ingestion import ingestion_agent_node
from src.agents.workers.search import search_agent_node


def create_audit_workflow() -> StateGraph:
    """
    Defines the nodes and sequential routing edges of the multi-agent audit pipeline.
    Returns an uncompiled StateGraph, allowing dynamic injection of state savers later.
    """
    workflow = StateGraph(AuditState)

    # Register specialized worker nodes into the graph
    workflow.add_node("ingestion_agent", ingestion_agent_node)
    workflow.add_node("search_agent", search_agent_node)
    workflow.add_node("auditor_agent", auditor_agent_node)
    workflow.add_node("governance_agent", governance_agent_node)

    # Establish the deterministic, sequential execution flow
    workflow.add_edge(START, "ingestion_agent")
    workflow.add_edge("ingestion_agent", "search_agent")
    workflow.add_edge("search_agent", "auditor_agent")
    workflow.add_edge("auditor_agent", "governance_agent")
    workflow.add_edge("governance_agent", END)

    return workflow


# Export the uncompiled workflow blueprint to be imported and compiled by the main server
audit_workflow = create_audit_workflow()
