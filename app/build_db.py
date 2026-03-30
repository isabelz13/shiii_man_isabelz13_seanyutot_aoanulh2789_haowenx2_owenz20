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
    password TEXT,
    equipped_weapon TEXT,
    level INTEGER DEFAULT 1,
    xp INTEGER DEFAULT 0,
    health INTEGER DEFAULT 100,
    country TEXT DEFAULT 'USA',
    balance INTEGER DEFAULT 100
);""")

c.executescript("""
DROP TABLE IF EXISTS fish;
CREATE TABLE fish (
    scientific_name TEXT,
    owner INTEGER,
    number_caught INTEGER DEFAULT 1,
    number_owned INTEGER DEFAULT 1,
    FOREIGN KEY (owner) REFERENCES profiles(id)
);""")

c.executescript("""
DROP TABLE IF EXISTS weapons;
CREATE TABLE weapons (
    name TEXT,
    owner INTEGER,
    number_owned INTEGER DEFAULT 1,
    durability INTEGER,
    FOREIGN KEY (owner) REFERENCES profiles(id)
);""")

c.executescript("""
DROP TABLE IF EXISTS achievements;
CREATE TABLE achievements (
    name TEXT,
    description TEXT,
    user INTEGER,
    time_received DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user) REFERENCES profiles(id)
);""")

db.commit()
db.close()
