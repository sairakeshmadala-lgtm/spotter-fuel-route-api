import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parent

INPUT = BASE / "best-station-matches.csv"
OUTPUT = BASE / "verified-match-candidates.csv"

print("Loading best station matches...")

df = pd.read_csv(INPUT)

# Keep candidates with similarity score >= 80
high = df[df["Match Score"] >= 80].copy()

# Remove records without usable coordinates
high = high.dropna(
    subset=["Longitude Min", "Latitude Min", "Longitude Max", "Latitude Max"]
)

# Calculate approximate center of each bounding box
high["Longitude"] = (
    high["Longitude Min"] + high["Longitude Max"]
) / 2

high["Latitude"] = (
    high["Latitude Min"] + high["Latitude Max"]
) / 2

high.to_csv(OUTPUT, index=False)

print("\nCANDIDATE FILTER COMPLETED")
print("High similarity candidates:", len(df[df["Match Score"] >= 80]))
print("Candidates with coordinates:", len(high))
print("Output:", OUTPUT)