from typing import TypedDict, List, Optional, Literal, Dict, Any


Stage = Literal[
    "await_question",
    "await_concept",
    "await_variable",
    "await_geo_level",
    "await_geo_location",
    "done",
]


class State(TypedDict, total=False):
    stage: Stage

    question: str
    candidate_concepts: List[str]

    # Set by app.py before invoking the subgraph; consumed by pick_concept.
    _user_input: str

    selected_concept: Optional[str]
    _concept_decision: str          # yes | refine | no, used by the subgraph
    refined_question: Optional[str]
    _last_llm_debug: Dict[str, Any] # raw LLM output from last pick, for debugging

    candidate_variables: List[Dict[str, Any]]
    selected_variable: Optional[str]   # Census var code, e.g. B19013_001E

    granularity: Optional[str]
    geography_code: Optional[str]

    census_url: Optional[str]
    results: Optional[List[Dict[str, Any]]]