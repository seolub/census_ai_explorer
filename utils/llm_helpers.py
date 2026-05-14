import json
from openai import OpenAI

client = OpenAI()
MODEL = "gpt-4o-mini"


def _ask_json(prompt, max_tokens=50):
    # response_format=json_object forces valid JSON. Without it the model
    # sometimes wraps the output in markdown fences or adds a preamble.
    r = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "Respond with ONLY valid JSON, no explanations."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    return json.loads(r.choices[0].message.content)


def interpret_user_response_1(user_response):
    """Extract a 1-based number from the user's reply, or null if there isn't one."""
    prompt = f"""
    Extract the row number the user picked from a numbered list. ANY of these
    mean they picked N: "N", "yes N", "#N", "number N", "row N", "row number N",
    "option N", "the Nth", "the Nth one".

    If the user's reply does NOT clearly name a row number, return null.

    Examples:
    - "2" → 2
    - "yes 3" → 3
    - "the second" → 2
    - "try housing instead" → null  (no row number)
    - "what is the population" → null  (no row number)
    - "none of these" → null

    Return ONLY: {{"number": integer or null}}

    User: {user_response!r}
    """.strip()
    raw = _ask_json(prompt)
    num = raw.get("number")
    return {"index": (num - 1) if isinstance(num, int) else None}


def interpret_user_response_2(user_response):
    """Parse the user's choice of geography level."""
    prompt = f"""
    Pick ONE Census geography level from: state, county, tract, block group, zcta5, place.

    Aliases: states→state, counties→county, tracts/census tracts→tract,
    block groups→block group, zip codes/zcta/zctas→zcta5, cities/places/towns→place.

    Default to "county" if unclear.

    Return ONLY: {{"granularity": "<one of the six values>"}}

    User: {user_response!r}
    """.strip()
    return _ask_json(prompt, max_tokens=30)


def interpret_user_response_3(user_response, granularity):
    """Parse the user's location into a Census API geography code."""
    # We tell the model exactly which prefix to start with — granularity is set
    # deterministically by the previous stage, the LLM only fills in the FIPS.
    # FIPS baked into the prompt — fine for the MVP. TODO: static dict later.
    formats = {
        "state":       'Output MUST start with "state:". Format: "state:<FIPS2>"',
        "county":      ('Output MUST start with "county:". Format: '
                        '"county:*&in=state:<FIPS2>" or "county:<FIPS5>&in=state:<FIPS2>"'),
        "tract":       ('Output MUST start with "tract:". Format: '
                        '"tract:*&in=state:<FIPS2>" or "tract:*&in=state:<FIPS2>+county:<FIPS5>"'),
        "block group": ('Output MUST start with "block group:". Format: '
                        '"block group:*&in=state:<FIPS2>" or '
                        '"block group:*&in=state:<FIPS2>+county:<FIPS5>"'),
        "place":       'Output MUST start with "place:". Format: "place:*&in=state:<FIPS2>"',
        "zcta5":       ('Output MUST be exactly "zip code tabulation area:*". '
                        'No state filter is supported.'),
    }
    rule = formats.get(granularity, formats["county"])

    prompt = f"""
    The user has chosen granularity = {granularity!r}. Build a Census API geography code.

    {rule}

    Add +county:<FIPS5> ONLY when the user explicitly names a county. If they only
    name a state, omit the county part.

    Common FIPS:
    Colorado=08, Denver county=08031, Boulder=08013, Jefferson=08059, Arapahoe=08005,
    California=06, Texas=48, New York=36, Florida=12, Illinois=17, Cook county (IL)=17031.

    If you don't know the state's FIPS, default to Colorado (08).

    Return ONLY: {{"geography_code": "<string starting with the required prefix>"}}

    User said: {user_response!r}
    """.strip()
    return _ask_json(prompt, max_tokens=80)