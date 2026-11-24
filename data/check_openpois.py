import duckdb

BASE = "s3://us-west-2.opendata.source.coop/henryspatialanalysis/openpois"
FILE = f"{BASE}/latest/conflated-parquet/**/*.parquet"

con = duckdb.connect()
con.execute("INSTALL httpfs;")
con.execute("LOAD httpfs;")

query = f"""
SELECT
    name,
    brand,
    addr_city,
    addr_state,
    addr_country,
    shared_label,
    bbox.xmin AS longitude_min,
    bbox.ymin AS latitude_min,
    bbox.xmax AS longitude_max,
    bbox.ymax AS latitude_max
FROM read_parquet('{FILE}', hive_partitioning=true)
WHERE
    upper(coalesce(addr_country, '')) = 'US'
    AND lower(coalesce(shared_label, '')) LIKE '%gas station%'
    AND bbox IS NOT NULL
"""

print("Exporting US fuel stations...")

try:
    con.execute(f"""
        COPY ({query})
        TO 'data/openpois-us-fuel.csv'
        (HEADER, DELIMITER ',');
    """)

    count = con.execute(
        "SELECT COUNT(*) FROM read_csv_auto('data/openpois-us-fuel.csv')"
    ).fetchone()[0]

    print("SUCCESS!")
    print("Exported records:", count)
    print("File: data/openpois-us-fuel.csv")

except Exception as error:
    print("ERROR:", error)