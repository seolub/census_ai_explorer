# Census Chat

A natural-language interface to the US Census Bureau's ACS 5-year API. Ask a
question like *"how much do people make?"*, get walked through picking a
variable and a geography, and download the results as CSV.

Built with Streamlit, LangGraph, OpenAI (gpt-4o-mini), and Chroma for semantic
search over the ~3k variables in the Census catalog.

## Quick Demo (click image for video)
[![Census Chat demo](https://img.youtube.com/vi/kn7ZUshZFgI/hqdefault.jpg)](https://youtu.be/kn7ZUshZFgI)

## Quick start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Add your keys
cp .env.example .env
# edit .env — needs OPENAI_API_KEY, optional CENSUS_API_KEY

# 3. Build the vector index over Census concepts (one-time, ~2 minutes)
python build_vector_index.py

# 4. Run
streamlit run app.py
```

The Census API works without a key for low-volume use; get one for free at
<https://api.census.gov/data/key_signup.html> if you hit rate limits.

## How it works

The user walks through six stages:

1. **Ask a question.** Free-form, e.g. *"median household income"*.
2. **Pick a concept** from a semantic-search shortlist of ~15 ACS concepts.
   Type a row number to pick, or any other text to refine the search.
3. **Pick a variable** under that concept (e.g. `B19013_001E` for the
   headline median, vs. breakdowns by race/sex/age).
4. **Choose a geography level**: state, county, tract, block group, place, zcta5.
5. **Specify the location**: "Colorado", "Denver county, CO", etc.
6. **Get results** as a table, downloadable as CSV.

## Architecture

```
app.py              Streamlit UI + explicit stage machine
state.py            TypedDict that defines the conversation state
nodes.py            Pure State -> State functions, one per workflow step
graph.py            LangGraph subgraph for the one piece that needs it
                    (the "refine" cycle at the concept-picking stage)
utils/
  llm_helpers.py    Three LLM parsers — number, level, location
  matching.py       Chroma vector search over concept strings
  census_api.py     Variable catalog + query execution
build_vector_index.py   One-time index build
```

### Workflow

Most of the workflow is a linear wizard — six stages, one path through — so
`app.py` drives the stages directly. The one place I let LangGraph's runtime
actually run is the concept-picking subgraph in `graph.py`. Picking a concept
has a cycle: if the user types a new search instead of a row number, the
workflow loops back to the vector search with the new query. That cycle is
exactly what state-machine frameworks are for.

The rest of the stages are calls in `app.py`. 

## Limitations

- ACS 5-year only. The Census publishes many datasets (decennial, ACS 1-year,
  PEP, etc.) — adding them is mostly more entries in `census_api.py` plus
  surfacing the choice in the UI.
- US only.
- The vector index is built once at setup time. Census variable catalogs do
  change between years, so re-running `build_vector_index.py` after each update keeps
  the search fresh.
