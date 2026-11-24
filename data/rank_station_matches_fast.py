import pandas as pd
import re
from pathlib import Path
from rapidfuzz import fuzz

BASE = Path(__file__).resolve().parent

fuel = pd.read_csv(BASE / "clean-fuel-stations.csv")
poi = pd.read_csv(BASE / "openpois-us-fuel.csv", low_memory=False)

def clean(value):
    if pd.isna(value):
        return ""
    return re.sub(r"[^a-z0-9]", "", str(value).lower())

STATE_NAMES = {
    "texas": "tx",
    "california": "ca",
    "florida": "fl",
    "newyork": "ny",
    "colorado": "co",
    "alabama": "al",
    "ohio": "oh",
    "georgia": "ga",
    "virginia": "va",
    "indiana": "in",
    "mississippi": "ms",
    "tennessee": "tn",
    "newjersey": "nj",
    "northcarolina": "nc",
    "southcarolina": "sc",
    "newmexico": "nm",
    "pennsylvania": "pa",
    "arkansas": "ar",
    "oklahoma": "ok",
    "nevada": "nv",
    "washington": "wa",
    "missouri": "mo",
    "newhampshire": "nh",
    "minnesota": "mn",
    "connecticut": "ct",
    "districtcolumbia": "dc",
}

def state_clean(value):
    key = clean(value)
    return STATE_NAMES.get(key, key)

fuel["city_key"] = fuel["City"].apply(clean)
poi["city_key"] = poi["addr_city"].apply(clean)

fuel["state_key"] = fuel["State"].apply(state_clean)
poi["state_key"] = poi["addr_state"].apply(state_clean)

fuel["name_key"] = fuel["Truckstop Name"].apply(clean)
poi["name_key"] = poi["name"].apply(clean)
poi["brand_key"] = poi["brand"].apply(clean)

# Build city/state groups once
groups = {
    key: group
    for key, group in poi.groupby(["city_key", "state_key"])
}

results = []

print("Starting fast station matching...")

for _, station in fuel.iterrows():
    key = (station["city_key"], station["state_key"])
    candidates = groups.get(key)

    if candidates is None or candidates.empty:
        continue

    for _, candidate in candidates.iterrows():
        station_name = station["name_key"]

        name_score = fuzz.token_set_ratio(
            station_name, candidate["name_key"]
        ) if station_name and candidate["name_key"] else 0

        brand_score = fuzz.token_set_ratio(
            station_name, candidate["brand_key"]
        ) if station_name and candidate["brand_key"] else 0

        score = max(name_score, brand_score)

        results.append({
            "OPIS Truckstop ID": station["OPIS Truckstop ID"],
            "Truckstop Name": station["Truckstop Name"],
            "City": station["City"],
            "State": station["State"],
            "Retail Price": station["Retail Price"],
            "POI Name": candidate["name"],
            "POI Brand": candidate["brand"],
            "Match Score": score,
            "Longitude Min": candidate["longitude_min"],
            "Latitude Min": candidate["latitude_min"],
            "Longitude Max": candidate["longitude_max"],
            "Latitude Max": candidate["latitude_max"],
        })

output = pd.DataFrame(results)

if not output.empty:
    output = output.sort_values(
        ["OPIS Truckstop ID", "Match Score"],
        ascending=[True, False]
    )

output.to_csv(BASE / "ranked-station-candidates-fast.csv", index=False)

print("\nFAST MATCHING COMPLETED")
print("Candidate records:", len(output))
print(
    "High similarity candidates (80+):",
    (output["Match Score"] >= 80).sum() if not output.empty else 0
)
print("Output: data/ranked-station-candidates-fast.csv")