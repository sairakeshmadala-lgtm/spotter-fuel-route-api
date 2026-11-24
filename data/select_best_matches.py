import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parent

INPUT = BASE / "ranked-station-candidates-fast.csv"
OUTPUT = BASE / "best-station-matches.csv"

print("Loading ranked candidates...")

df = pd.read_csv(INPUT)

print("Total candidates:", len(df))

# Select highest-scoring candidate for each OPIS station
df = df.sort_values(
    ["OPIS Truckstop ID", "Match Score"],
    ascending=[True, False]
)

best = df.drop_duplicates(
    subset=["OPIS Truckstop ID"],
    keep="first"
).copy()

# Keep high-similarity candidates for review
best["Match Status"] = best["Match Score"].apply(
    lambda score: "REVIEW_REQUIRED" if score >= 80 else "LOW_CONFIDENCE"
)

best.to_csv(OUTPUT, index=False)

print("\nBEST MATCH SELECTION COMPLETED")
print("Best candidates:", len(best))
print(
    "High similarity:",
    (best["Match Score"] >= 80).sum()
)
print(
    "Low similarity:",
    (best["Match Score"] < 80).sum()
)
print("Output:", OUTPUT)