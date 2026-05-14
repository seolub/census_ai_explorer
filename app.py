import streamlit as st
import pandas as pd
from dotenv import load_dotenv

from state import State
from graph import concept_subgraph
from nodes import (
    find_concepts, list_variables, pick_variable,
    pick_level, pick_location, run_query,
)

load_dotenv()
st.set_page_config(page_title="Census Chat", page_icon="🤖", layout="wide")
st.title("🤖 Census Chat")
st.caption("Ask a question about Census data — I'll walk you through finding the right variable.")

# Streamlit reruns the whole script on every interaction, so anything that
# needs to survive between turns goes in session_state.
if "messages" not in st.session_state:
    st.session_state.messages = []
if "state" not in st.session_state:
    st.session_state.state = State(stage="await_question")


def reset():
    st.session_state.messages = []
    st.session_state.state = State(stage="await_question")


with st.sidebar:
    st.button("🔄 Start over", on_click=reset)

    # Show a download button whenever we have results — rendering from
    # session_state means it persists across reruns, so the user can grab
    # the CSV anytime, not just on the turn it first appeared.
    results = st.session_state.state.get("results")
    if results:
        csv = pd.DataFrame(results).to_csv(index=False).encode()
        var = st.session_state.state.get("selected_variable", "census")
        gran = st.session_state.state.get("granularity", "data")
        st.download_button("📥 Download CSV", csv, f"{var}_{gran}.csv", "text/csv")

    # Debug: what did the LLM say to the last pick attempt? Useful when
    # the parser keeps refusing valid inputs.
    dbg = st.session_state.state.get("_last_llm_debug")
    if dbg:
        with st.expander("🐛 last LLM parse"):
            st.json(dbg)

    st.markdown("---")
    st.markdown(
        "1. Ask a question\n"
        "2. Pick a concept by number\n"
        "3. Pick a specific variable\n"
        "4. Choose a geography level\n"
        "5. Specify the state/county\n"
        "6. Download the result"
    )


def render_table(df, picker):
    # Picker tables show the 1-based pandas index so users can reply "2".
    # Results tables hide it (just noise).
    st.dataframe(df, use_container_width=True, hide_index=not picker, height=400)


def add(role, text, df=None, picker=False):
    st.session_state.messages.append({"role": role, "text": text, "df": df, "picker": picker})
    with st.chat_message(role):
        st.markdown(text)
        if df is not None:
            render_table(df, picker)


# Replay history on every rerun.
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["text"])
        if m["df"] is not None:
            render_table(m["df"], m["picker"])


def numbered(items, label):
    # 1-based index so "yes 2" lines up with what the user sees in the table.
    if label == "Concept":
        df = pd.DataFrame({"Concept": items})
    else:
        df = pd.DataFrame(items)
    df.index = pd.RangeIndex(start=1, stop=len(df) + 1)
    return df


def advance(user_input):
    s = st.session_state.state
    stage = s["stage"]

    try:
        if stage == "await_question":
            s = find_concepts(s, user_input)
            s["question"] = user_input
            s["stage"] = "await_concept"
            add("assistant",
                "Here are concepts matching your question. Reply with the row number (e.g. `2`), "
                "or describe a different search if none fit (e.g. `try housing instead`).",
                df=numbered(s["candidate_concepts"], "Concept"), picker=True)

        elif stage == "await_concept":
            # Hand off to the subgraph. It runs pick_concept and, if the user
            # didn't give a number, it cycles through find_concepts with their
            # reply as the new search query before exiting.
            s = concept_subgraph.invoke({**s, "_user_input": user_input})
            decision = s.get("_concept_decision")

            if decision == "yes" and s.get("selected_concept"):
                s = list_variables(s)
                s["stage"] = "await_variable"
                add("assistant",
                    f"**{s['selected_concept']}** has {len(s['candidate_variables'])} variables. "
                    "Which row do you want? `_001E` codes are usually the headline total; "
                    "other rows are breakdowns by sex, age, race, etc.",
                    df=numbered(s["candidate_variables"], "variable"), picker=True)
            else:
                # refine: subgraph already ran a fresh search; show new candidates
                add("assistant",
                    f"Searched for `{s['question']}`. Here are matching concepts:",
                    df=numbered(s["candidate_concepts"], "Concept"), picker=True)

        elif stage == "await_variable":
            before = s.get("selected_variable")
            s = pick_variable(s, user_input)
            if s.get("selected_variable") == before:
                add("assistant", "I couldn't parse that — please reply with a row number.")
            else:
                s["stage"] = "await_geo_level"
                add("assistant",
                    f"Using `{s['selected_variable']}`. What level of geography? "
                    "Options: `state`, `county`, `tract`, `block group`, `place`, `zcta5`.")

        elif stage == "await_geo_level":
            s = pick_level(s, user_input)
            s["stage"] = "await_geo_location"
            level = s["granularity"]
            if level == "state":
                prompt_text = "Which state? (e.g. `Colorado`)"
            elif level in ("tract", "block group"):
                prompt_text = (f"Which state? (e.g. `Colorado`). "
                               "You can also narrow to a specific county "
                               "(e.g. `Denver county, Colorado`).")
            elif level == "zcta5":
                prompt_text = "ZCTA5 queries return all ZIP areas. Reply `go` to continue."
            else:
                prompt_text = f"Which state? (e.g. `Colorado`, or `Denver county, CO`)"
            add("assistant", f"Granularity: **{level}**. {prompt_text}")

        elif stage == "await_geo_location":
            s = pick_location(s, user_input)
            s = run_query(s)
            s["stage"] = "done"
            add("assistant",
                f"✅ Done!\n\n"
                f"- **Concept:** {s['selected_concept']}\n"
                f"- **Variable:** `{s['selected_variable']}`\n"
                f"- **Geography:** `{s['geography_code']}`\n"
                f"- **URL:** `{s['census_url']}`\n\n"
                f"Use the sidebar to download as CSV.",
                df=pd.DataFrame(s["results"]))

        elif stage == "done":
            add("assistant", "All done — hit *Start over* in the sidebar to ask another question.")

    except Exception as e:
        # Catch-all so a bad LLM response or API hiccup doesn't kill the session.
        import traceback
        traceback.print_exc()
        add("assistant", f"⚠️ Exception: `{type(e).__name__}: {e}`")

    st.session_state.state = s


if prompt := st.chat_input("Type your message..."):
    add("user", prompt)
    advance(prompt)