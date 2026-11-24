import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parent

INPUT = BASE / "verified-match-candidates.csv"
OUTPUT = BASE / "validated-station-coordinates.csv"

print("Loading station candidates...")

df = pd.read_csv(INPUT)

# Check coordinate ranges
valid = df[
    df["Longitude"].between(-125, -66)
    & df["Latitude"].between(24, 50)
].copy()

# Remove duplicate OPIS stations
valid = valid.sort_values(
    ["OPIS Truckstop ID", "Match Score"],
    ascending=[True, False]
)

valid = valid.drop_duplicates(
    subset=["OPIS Truckstop ID"],
    keep="first"
)

valid.to_csv(OUTPUT, index=False)

print("\nCOORDINATE CHECK COMPLETED")
print("Input candidates:", len(df))
print("Valid coordinate records:", len(valid))
print("Unique OPIS stations:", valid["OPIS Truckstop ID"].nunique())
print("Output:", OUTPUT)