import pandas as pd
import re
from pathlib import Path
from rapidfuzz import fuzz, process

BASE = Path(__file__).resolve().parent

fuel = pd.read_csv(BASE / "clean-fuel-stations.csv")
poi = pd.read_csv(BASE / "openpois-us-fuel.csv", low_memory=False)


def clean(value):
    if pd.isna(value):
        return ""
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def state_clean(value):
    value = clean(value)
    aliases = {
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
        "district of columbia": "dc",
        "districtcolumbia": "dc",
    }
    return aliases.get(value, value)


fuel["city_key"] = fuel["City"].apply(clean)
poi["city_key"] = poi["addr_city"].apply(clean)

fuel["state_key"] = fuel["State"].apply(state_clean)
poi["state_key"] = poi["addr_state"].apply(state_clean)

fuel["name_key"] = fuel["Truckstop Name"].apply(clean)
poi["name_key"] = poi["name"].apply(clean)
poi["brand_key"] = poi["brand"].apply(clean)

results = []

print("Ranking station candidates...")

for _, station in fuel.iterrows():
    candidates = poi[
        (poi["city_key"] == station["city_key"])
        & (poi["state_key"] == station["state_key"])
    ]

    if candidates.empty:
        continue

    for _, candidate in candidates.iterrows():
        name_score = fuzz.token_set_ratio(
            station["name_key"],
            candidate["name_key"]
        ) if station["name_key"] and candidate["name_key"] else 0

        brand_score = fuzz.token_set_ratio(
            station["name_key"],
            candidate["brand_key"]
        ) if station["name_key"] and candidate["brand_key"] else 0

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

output.to_csv(BASE / "ranked-station-candidates.csv", index=False)

print("Ranking completed.")
print("Candidate records:", len(output))
print("High name similarity (80+):", (output["Match Score"] >= 80).sum() if not output.empty else 0)
print("Output: data/ranked-station-candidates.csv")