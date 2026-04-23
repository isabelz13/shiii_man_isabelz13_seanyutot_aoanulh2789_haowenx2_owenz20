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
    password TEXT,
    total_maps INTEGER,
    wins INTEGER
);

CREATE TABLE saved_maps (
    map_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    map_name TEXT UNIQUE,
    player_party TEXT,
    district1 INTEGER,
    district2 INTEGER,
    district3 INTEGER,
    district4 INTEGER,
    district5 INTEGER,
    district6 INTEGER,
    district7 INTEGER,
    district8 INTEGER,
    district9 INTEGER,
    district10 INTEGER,
    district11 INTEGER,
    district12 INTEGER,
    district13 INTEGER,
    district14 INTEGER,
    district15 INTEGER,
    district16 INTEGER,
    district17 INTEGER,
    district18 INTEGER,
    district19 INTEGER,
    district20 INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES profiles(id)
);
""")


db.commit()

db.close()

print("Database setup complete.")
