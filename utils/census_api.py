import os
import requests
import pandas as pd
 
BASE_URL = "https://api.census.gov/data"
API_KEY = os.environ.get("CENSUS_API_KEY", "")
 
 
def get_variables_json(year=2024, dataset="acs/acs5") -> pd.DataFrame:
    url = f"{BASE_URL}/{year}/{dataset}/variables.json"
    if API_KEY:
        url += f"?key={API_KEY}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    df = pd.DataFrame.from_dict(r.json()["variables"], orient="index").reset_index()
    return df.rename(columns={"index": "name"})
 
 
def execute_query(variable, geography_code, year=2024, dataset="acs/acs5"):
    """Run a Census query. Returns (url, dataframe)."""
    # geography_code already includes the &in= bit if needed (e.g. county:*&in=state:08)
    var_str = f"NAME,{variable}"
    url = f"{BASE_URL}/{year}/{dataset}?get={var_str}&for={geography_code}"
    if API_KEY:
        url += f"&key={API_KEY}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    data = r.json()
    return url, pd.DataFrame(data[1:], columns=data[0])