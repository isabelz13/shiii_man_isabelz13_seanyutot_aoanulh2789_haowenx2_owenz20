# Isabel Zheng, Araf Hoque, Sean Takahashi, Haowen Xiao, Owen Zeng
# shiii_man
# SoftDev
# P04
# 2026-04-20m

import sqlite3

DB_FILE = "data.db"

db = sqlite3.connect(DB_FILE)
c = db.cursor()

c.executescript("""
DROP TABLE IF EXISTS profiles;
CREATE TABLE profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT
);""")

c.executescript("""
DROP TABLE IF EXISTS saved_maps;
CREATE TABLE saved_maps (
    map_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    map_name TEXT UNIQUE,
    created_at TIMESTAMP CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES profiles(id)
);""")

c.executescript("""
DROP TABLE IF EXISTS map_gmed;
CREATE TABLE map_gmed (
    map_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    election_district INTEGER,
    assembly_district INTEGER,
    assigned_district_id INTEGER,
    FOREIGN KEY (user_id) REFERENCES profiles(id)
);""")


db.commit()
db.close()
