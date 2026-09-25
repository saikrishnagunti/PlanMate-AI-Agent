from langgraph.graph import StateGraph, START, END
from src.state import PlanMateState
from src.agents.nodes import (
    intent_router_node,
    weather_node,
    scout_node,
    critic_node,
    synthesizer_node
)

def should_retry(state: PlanMateState) -> str:
    """Conditional edge: loops back if critic detected a mismatch, up to limit."""
    if state.get("validation_status") == "retry":
        return "scout_node"
    return "synthesizer_node"

def build_planmate_graph():
    builder = StateGraph(PlanMateState)

    # 1. Add Nodes
    builder.add_node("router", intent_router_node)
    builder.add_node("weather_node", weather_node)
    builder.add_node("scout_node", scout_node)
    builder.add_node("critic_node", critic_node)
    builder.add_node("synthesizer_node", synthesizer_node)

    # 2. Add Linear & Parallel Edges
    builder.add_edge(START, "router")
    builder.add_edge("router", "weather_node")
    builder.add_edge("weather_node", "scout_node")
    builder.add_edge("scout_node", "critic_node")

    # 3. Add Cyclic Validation Edge (Scout <-> Critic)
    builder.add_conditional_edges(
        "critic_node",
        should_retry,
        {
            "scout_node": "scout_node",
            "synthesizer_node": "synthesizer_node"
        }
    )

    builder.add_edge("synthesizer_node", END)

    return builder.compile()

# Pre-compiled executable graph instance
planmate_graph = build_planmate_graph()