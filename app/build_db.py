# Isabel Zheng, Araf Hoque, Sean Takahashi, Haowen Xiao, Owen Zeng
# shiii_man
# SoftDev
# P04
# 2026-04-20m

import sqlite3
import pandas as pd
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_FOLDER = BASE_DIR / "data"

DB_FILE = "data.db"

db = sqlite3.connect(DB_FILE)
cur = db.cursor()

# Wiping the old tables and rebuild everything from scratch
cur.executescript("""
DROP TABLE IF EXISTS profiles;
DROP TABLE IF EXISTS saved_maps;
DROP TABLE IF EXISTS map_gmed;
DROP TABLE IF EXISTS income;
DROP TABLE IF EXISTS zipcodes;
DROP TABLE IF EXISTS election;
DROP TABLE IF EXISTS voter;

CREATE TABLE profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT
);

CREATE TABLE saved_maps (
    map_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    map_name TEXT UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES profiles(id)
);

CREATE TABLE map_gmed (
    map_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    election_district INTEGER,
    assembly_district INTEGER,
    assigned_district_id INTEGER,
    FOREIGN KEY (user_id) REFERENCES profiles(id)
);

CREATE TABLE income (
    zip TEXT,
    median_income REAL
);

CREATE TABLE zipcodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    geojson TEXT
);

CREATE TABLE election (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    geojson TEXT
);

CREATE TABLE voter (
    AssemblyDistrict INTEGER,
    ElectionDistrict INTEGER,
    PoliticalParty TEXT
);
""")

# Load the income csv into a dataframe
income_df = pd.read_csv(DATA_FOLDER / "IncomeData.csv")

# Make sure every zip code stays 5 digits
income_df["ZIP"] = income_df["ZIP"].astype(str).str.zfill(5)

# Add each income row into the income table
for _, row in income_df.iterrows():
    cur.execute(
        "INSERT INTO income (zip, median_income) VALUES (?, ?)",
        (row["ZIP"], row["MedianIncome"])
    )

with open(DATA_FOLDER / "ZipCode.geojson", "r", encoding="utf-8") as f:
    zip_data = json.load(f)

# Store each zipcode feature as its own row
for feature in zip_data["features"]:
    cur.execute(
        "INSERT INTO zipcodes (geojson) VALUES (?)",
        (json.dumps(feature),)
    )

with open(DATA_FOLDER / "nyed_18d.geojson", "r", encoding="utf-8") as f:
    election_data = json.load(f)

# Store each election district feature as its own row
for feature in election_data["features"]:
    cur.execute(
        "INSERT INTO election (geojson) VALUES (?)",
        (json.dumps(feature),)
    )

# Loading the voter registration csv
voter_df = pd.read_csv(DATA_FOLDER / "VoteRegistration2018.csv")

# Keeping the column names clean and consistent
voter_df = voter_df.rename(columns={
    "AssemblyDistrict": "AssemblyDistrict",
    "ElectionDistrict": "ElectionDistrict",
    "PoliticalParty": "PoliticalParty"
})

# Keeping only the columns we actually need and drop empty rows
voter_df = voter_df[["AssemblyDistrict", "ElectionDistrict", "PoliticalParty"]].dropna()

# Adding each voter row into the voter table
for _, row in voter_df.iterrows():
    cur.execute(
        "INSERT INTO voter (AssemblyDistrict, ElectionDistrict, PoliticalParty) VALUES (?, ?, ?)",
        (int(row["AssemblyDistrict"]), int(row["ElectionDistrict"]), str(row["PoliticalParty"]).strip())
    )

db.commit()

# Debugging prints checking if thedata is actually loaded into the tables
print("TABLES IN BUILDER DB:")
print(cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())
print("income count:", cur.execute("SELECT COUNT(*) FROM income").fetchone()[0])
print("zipcodes count:", cur.execute("SELECT COUNT(*) FROM zipcodes").fetchone()[0])
print("election count:", cur.execute("SELECT COUNT(*) FROM election").fetchone()[0])
print("voter count:", cur.execute("SELECT COUNT(*) FROM voter").fetchone()[0])

db.close()

print("Database setup complete.")
