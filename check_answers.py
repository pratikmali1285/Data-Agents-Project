"""
check_answers.py  -  prints the correct answer to every demo question

It runs the hand-written SQL in answers.sql, so you can check the agent's numbers on camera.

RUN IT
  python check_answers.py
"""
import os
from decimal import Decimal

import duckdb

FOLDER = os.path.dirname(os.path.abspath(__file__))
db = duckdb.connect(f"{FOLDER}/warehouse.duckdb", read_only=True)

# answers.sql holds one query per question, separated by ";"
queries = open(f"{FOLDER}/answers.sql").read().split(";")

for query in queries:
    if "SELECT" not in query:
        continue
    title = [line for line in query.splitlines() if line.startswith("-- Q")][0]
    result = db.execute(query)
    columns = [col[0] for col in result.description]

    print("\n" + title.lstrip("- "))
    for row in result.fetchall():
        # numbers get thousands separators so they are easy to read
        values = [f"{v:,}" if isinstance(v, (int, float, Decimal)) else str(v) for v in row]
        print("   " + "  |  ".join(f"{col} = {value}" for col, value in zip(columns, values)))
