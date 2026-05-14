from state import State
from utils.census_api import get_variables_json, execute_query
from utils.matching import semantic_candidates_from_db
from utils.llm_helpers import (
    interpret_user_response_1,
    interpret_user_response_2,
    interpret_user_response_3,
)
 
# Loaded once at import. ~5MB of JSON, don't want to refetch per request.
VARS_DF = get_variables_json()
 
 
def find_concepts(state: State, question=None) -> State:
    # Pull from refined_question if the subgraph cycled, else fall back to the param.
    q = state.get("refined_question") or question or state.get("question", "")
    return {**state,
            "candidate_concepts": semantic_candidates_from_db(q),
            "question": q,
            "refined_question": None}
 
 
def pick_concept(state: State, user_response=None) -> State:
    # When the subgraph runs this node directly it only passes state, so we
    # read the user's reply from _user_input. When app.py calls it for tests
    # or manually, user_response is set.
    reply = user_response if user_response is not None else state.get("_user_input", "")
    idx = interpret_user_response_1(reply).get("index")
    candidates = state.get("candidate_concepts", [])
 
    debug = {"reply": reply, "index": idx, "n_candidates": len(candidates)}
    import sys
    print(f"[pick_concept] {debug}", file=sys.stderr)
 
    # Valid number → user picked. No valid number → treat the input as a new
    # search query (refine). The "no decision" case doesn't exist here anymore.
    if isinstance(idx, int) and 0 <= idx < len(candidates):
        return {**state, "_concept_decision": "yes",
                "selected_concept": candidates[idx], "_last_llm_debug": debug}
    return {**state, "_concept_decision": "refine",
            "refined_question": reply, "_last_llm_debug": debug}
 
 
def list_variables(state: State) -> State:
    subset = VARS_DF[VARS_DF["concept"] == state["selected_concept"]]
    rows = [{"name": r["name"], "label": r.get("label", "")}
            for r in subset.to_dict(orient="records")]
    return {**state, "candidate_variables": rows}
 
 
def pick_variable(state: State, user_response) -> State:
    idx = interpret_user_response_1(user_response).get("index")
    candidates = state.get("candidate_variables", [])
    if isinstance(idx, int) and 0 <= idx < len(candidates):
        return {**state, "selected_variable": candidates[idx]["name"]}
    return state
 
 
def pick_level(state: State, user_response) -> State:
    return {**state, "granularity": interpret_user_response_2(user_response)["granularity"]}
 
 
def pick_location(state: State, user_response) -> State:
    gran = state["granularity"]
    code = interpret_user_response_3(user_response, granularity=gran)["geography_code"]
 
    # Sanity check: the code must start with the granularity prefix. Sometimes
    # the LLM ignores the level (e.g. user types "Illinois" at the tract stage
    # and it returns "state:17"). When this happens, prepend the right prefix
    # — the state FIPS in the LLM's output is still useful, just wrongly framed.
    expected_prefix = {
        "state":       "state:",
        "county":      "county:",
        "tract":       "tract:",
        "block group": "block group:",
        "place":       "place:",
        "zcta5":       "zip code tabulation area:",
    }.get(gran, "")
 
    if expected_prefix and not code.startswith(expected_prefix):
        # The LLM gave us a state:NN when we asked for e.g. tracts. Wrap it.
        if code.startswith("state:") and gran in ("tract", "block group", "county", "place"):
            code = f"{gran}:*&in={code}"
        elif gran == "zcta5":
            code = "zip code tabulation area:*"
 
    return {**state, "geography_code": code}
 
 
def run_query(state: State) -> State:
    url, df = execute_query(state["selected_variable"], state["geography_code"])
    return {**state, "census_url": url, "results": df.to_dict(orient="records")}