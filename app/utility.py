# Isabel Zheng, Araf Hoque, Sean Takahashi, Haowen Xiao, Owen Zeng
# shiii_man
# SoftDev
# P04
# 2026-04-20m

import sqlite3
import urllib.parse, urllib.error, urllib.request
import json
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

DB_FILE = "data.db"
db = sqlite3.connect(DB_FILE, check_same_thread=False)

def dictify(raw, c):
    output = []
    for row in raw:
        d = dict()
        for col in range(len(row)):
            d.update({c.description[col][0]: row[col]})
        output.append(d)
    return output


# data: "key": value}
def insert_query(table, data):
    c = db.cursor()
    placeholder = ["?"] * len(data)
    c.execute(f"INSERT INTO {table} {tuple(data.keys())} VALUES ({', '.join(placeholder)});", tuple(data.values()))
    c.close()
    db.commit()

# params: [val1, val2]
# returns [{'key1': val1}]
def general_query(query_string, params=()):
    c = db.cursor()
    c.execute(query_string, params)
    raw = c.fetchall()
    output = dictify(raw, c)
    c.close()
    db.commit()
    return output

def get_user(name):
    user = general_query(f"SELECT * FROM profiles WHERE username=?", [name])
    return None if len(user) == 0 else user[0]
