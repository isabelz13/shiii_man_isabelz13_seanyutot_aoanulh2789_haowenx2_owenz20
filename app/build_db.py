# Isabel Zheng, Araf Hoque, Sean Takahashi, Haowen Xiao, Owen Zeng
# shiii_man
# SoftDev
# P04
# 2026-04-20m

import sqlite3
import pandas as pd
import json 
from pathlib import Path

BASE_DIR = Path (__file__).resolve().parent.parent

data_folder = BASE_DIR/ "data"
DB_FILE = "data.db"
print("BASE DIR:", BASE_DIR)
print("FILES IN DATA FOLDER:")
print(list(data_folder.glob("*")))

print("LOOKING FOR FILE:", data_folder / "IncomeData.csv")
print("EXISTS:", (data_folder / "IncomeData.csv").exists())

db = sqlite3.connect(DB_FILE)
c = db.cursor()

c.executescript("""
CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT
);""")

c.executescript("""
CREATE TABLE IF NOT EXISTS saved_maps (
    map_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    map_name TEXT UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES profiles(id)
);""")

c.executescript("""
CREATE TABLE IF NOT EXISTS map_gmed (
    map_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    election_district INTEGER,
    assembly_district INTEGER,
    assigned_district_id INTEGER,
    FOREIGN KEY (user_id) REFERENCES profiles(id)
);""")

c.execute("""
CREATE TABLE IF NOT EXISTS income (
    zip TEXT,
    median_income REAL
);""")

c.execute("""
CREATE TABLE IF NOT EXISTS zipcodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    geojson TEXT
);""")

c.execute("""
CREATE TABLE IF NOT EXISTS election (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    geojson TEXT 
);""")

c.execute(""" 
CREATE TABLE IF NOT EXISTS voter (
    AssemblyDistrict INTEGER,
    ElectionDistrict INTEGER,
    PoliticalParty TEXT
);""") 

data_folder = Path("data")

count = c.execute("SELECT COUNT(*) FROM income").fetchone()[0]
if count == 0:
    df = pd.read_csv(data_folder / "IncomeData.csv")

    df["ZIP"] = df["ZIP"].astype(str).str.zfill(5)

    for _, row in df.iterrows():
        c.execute(
            "INSERT INTO income (zip, median_income) VALUES (?, ?)",
            (row["ZIP"], row["MedianIncome"])
        )

count = c.execute("SELECT COUNT(*) FROM zipcodes").fetchone()[0]
if count == 0:
    with open(data_folder / "ZipCode.geojson") as f:
        zip_data = json.load(f)

    for feature in zip_data["features"]:
        c.execute(
            "INSERT INTO zipcodes (geojson) VALUES (?)",
            (json.dumps(feature),)
        )

count = c.execute("SELECT COUNT(*) FROM election").fetchone()[0]
if count == 0:
    with open(data_folder / "nyed_18d.geojson") as f:
        elec_data = json.load(f)

    for feature in elec_data["features"]:
        c.execute(
            "INSERT INTO election (geojson) VALUES (?)",
            (json.dumps(feature),)
        )

db.commit()
db.close()

print("Database setup complete.")

db.commit()
db.close()
