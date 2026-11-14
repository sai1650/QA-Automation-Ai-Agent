from typing import Literal

from langgraph.graph import END

from app.graph.qa_state import QAState


def route_initial(state: QAState) -> Literal["analyze_requirements", "check_approval"]:
    return (
        "check_approval"
        if state.get("resume_node") == "check_approval"
        else "analyze_requirements"
    )


def route_after_node(state: QAState, next_node: str) -> str:
    return "handle_workflow_error" if state.get("errors") else next_node


def route_after_inspection_approval(state: QAState) -> str:
    if state.get("approval_status") == "REJECTED":
        return "handle_workflow_error"
    if state.get("workflow_status") == "WAITING_APPROVAL":
        return END
    if state.get("approval_phase") == "INSPECTION":
        return "inspect_website"
    if state.get("approval_phase") == "TEST_PLAN":
        return "coordinate_execution"
    return "handle_workflow_error"


def route_after_inspection(state: QAState) -> str:
    return route_after_node(state, "understand_website")


def route_after_generation(state: QAState) -> str:
    return route_after_node(state, "check_approval")


def route_after_coordination(state: QAState) -> str:
    return route_after_node(state, "retrieve_historical_knowledge")


def route_after_retrieval(state: QAState) -> str:
    return route_after_node(state, "analyze_bugs")


def route_after_bug_analysis(state: QAState) -> str:
    return route_after_node(state, "generate_report")
