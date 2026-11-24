import pandas as pd
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

FUEL_FILE = BASE_DIR / "clean-fuel-stations.csv"
POI_FILE = BASE_DIR / "openpois-us-fuel.csv"
OUTPUT_FILE = BASE_DIR / "matched-fuel-stations.csv"


def normalize(value):
    if pd.isna(value):
        return ""
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


print("Loading fuel price stations...")
fuel = pd.read_csv(FUEL_FILE)

print("Loading OpenPOIs stations...")
poi = pd.read_csv(POI_FILE, low_memory=False)

# Normalize city and state names
fuel["city_key"] = fuel["City"].apply(normalize)
poi["city_key"] = poi["addr_city"].apply(normalize)

fuel["state_key"] = fuel["State"].apply(normalize)
poi["state_key"] = poi["addr_state"].apply(normalize)

# Keep only records with usable location information
poi = poi[
    poi["city_key"].ne("")
    & poi["state_key"].ne("")
].copy()

print("Matching by city and state...")

matched = fuel.merge(
    poi,
    on=["city_key", "state_key"],
    how="inner",
    suffixes=("_fuel", "_poi")
)

# Keep useful columns
columns = [
    "OPIS Truckstop ID",
    "Truckstop Name",
    "City",
    "State",
    "Retail Price",
    "name",
    "brand",
    "longitude_min",
    "latitude_min",
    "longitude_max",
    "latitude_max",
]

matched = matched[columns].drop_duplicates()

matched.to_csv(OUTPUT_FILE, index=False)

print("\nMATCHING COMPLETED")
print("Original fuel stations:", len(fuel))
print("OpenPOIs records:", len(poi))
print("Matched records:", len(matched))
print("Output file:", OUTPUT_FILE)