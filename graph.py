from langgraph.graph import StateGraph, END, START
from state import State
from nodes import find_concepts, pick_concept
 
 
def _route_after_pick(state):
    if state.get("_concept_decision") == "refine":
        return "find_concepts"
    return END
 
 
def _build():
    g = StateGraph(State)
    g.add_node("find_concepts", find_concepts)
    g.add_node("pick_concept", pick_concept)
 
    g.add_edge(START, "pick_concept")
    g.add_conditional_edges("pick_concept", _route_after_pick,
                            {"find_concepts": "find_concepts", END: END})
    # After a refine pass we exit so app.py can show the new candidates
    # and wait for the next user reply.
    g.add_edge("find_concepts", END)
    return g.compile()
 
 
concept_subgraph = _build()