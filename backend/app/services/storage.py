from __future__ import annotations
import json, sqlite3
from .data import ROOT

DB=ROOT/"data/processed/runs.sqlite3"

def connection():
    DB.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(DB)
    db.execute("CREATE TABLE IF NOT EXISTS artifacts (id TEXT PRIMARY KEY, kind TEXT NOT NULL, body TEXT NOT NULL)")
    return db

def put(key,kind,value):
    with connection() as db: db.execute("INSERT OR REPLACE INTO artifacts VALUES (?,?,?)",(key,kind,json.dumps(value,allow_nan=False)))

def get(key,kind=None):
    with connection() as db: row=db.execute("SELECT kind,body FROM artifacts WHERE id=?",(key,)).fetchone()
    if row is None or (kind and row[0]!=kind): raise ValueError("Unknown or unavailable artifact id")
    return json.loads(row[1])
