from langgraph.graph import END, START, StateGraph

from app.ai.llm_provider import StructuredOutputProvider
from app.graph.qa_edges import (
    route_after_bug_analysis,
    route_after_coordination,
    route_after_generation,
    route_after_inspection,
    route_after_inspection_approval,
    route_after_node,
    route_after_retrieval,
    route_initial,
)
from app.graph.qa_nodes import create_qa_nodes
from app.graph.qa_state import QAState
from app.services.browser_inspection import BrowserInspectionService
from app.rag.service import KnowledgeService


def build_qa_graph(
    provider: StructuredOutputProvider,
    inspection_service: BrowserInspectionService,
    knowledge_service: KnowledgeService | None = None,
):
    nodes = create_qa_nodes(provider, inspection_service, knowledge_service)
    graph = StateGraph(QAState)
    for name, function in nodes.items():
        graph.add_node(name, function)

    graph.add_conditional_edges(
        START,
        route_initial,
        {
            "analyze_requirements": "analyze_requirements",
            "check_approval": "check_approval",
        },
    )
    graph.add_conditional_edges(
        "analyze_requirements",
        lambda state: route_after_node(state, "create_test_plan"),
        {
            "create_test_plan": "create_test_plan",
            "handle_workflow_error": "handle_workflow_error",
        },
    )
    graph.add_conditional_edges(
        "create_test_plan",
        lambda state: route_after_node(state, "check_approval"),
        {
            "check_approval": "check_approval",
            "handle_workflow_error": "handle_workflow_error",
        },
    )
    graph.add_conditional_edges(
        "check_approval",
        route_after_inspection_approval,
        {
            "inspect_website": "inspect_website",
            "coordinate_execution": "coordinate_execution",
            "handle_workflow_error": "handle_workflow_error",
            END: END,
        },
    )
    graph.add_conditional_edges(
        "inspect_website",
        route_after_inspection,
        {
            "understand_website": "understand_website",
            "handle_workflow_error": "handle_workflow_error",
        },
    )
    graph.add_conditional_edges(
        "understand_website",
        lambda state: route_after_node(state, "generate_test_cases"),
        {
            "generate_test_cases": "generate_test_cases",
            "handle_workflow_error": "handle_workflow_error",
        },
    )
    graph.add_conditional_edges(
        "generate_test_cases",
        route_after_generation,
        {
            "check_approval": "check_approval",
            "handle_workflow_error": "handle_workflow_error",
        },
    )
    graph.add_conditional_edges(
        "coordinate_execution",
        route_after_coordination,
        {
            "retrieve_historical_knowledge": "retrieve_historical_knowledge",
            "handle_workflow_error": "handle_workflow_error",
        },
    )
    graph.add_conditional_edges(
        "retrieve_historical_knowledge",
        route_after_retrieval,
        {
            "analyze_bugs": "analyze_bugs",
            "handle_workflow_error": "handle_workflow_error",
        },
    )
    graph.add_conditional_edges(
        "analyze_bugs",
        route_after_bug_analysis,
        {
            "generate_report": "generate_report",
            "handle_workflow_error": "handle_workflow_error",
        },
    )
    graph.add_edge("generate_report", END)
    graph.add_edge("handle_workflow_error", END)
    return graph.compile()
