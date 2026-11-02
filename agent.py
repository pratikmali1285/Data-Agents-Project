"""
agent.py  -  a data agent in about 100 lines

WHAT IT DOES
  You ask a question in plain English. The agent answers it by looking at the
  warehouse and running SQL, step by step, the way an analyst would.

HOW IT WORKS  (the loop from the video: plan, look, write, run, check)
  1. We send the LLM (on Groq) the question, plus a list of tools it is allowed to use.
  2. The LLM replies with either
       a) a tool request, for example  run_sql("SELECT COUNT(*) FROM orders"), or
       b) the final answer.
  3. If it asked for a tool, OUR code runs that tool on DuckDB and sends back the result.
  4. Repeat from step 2 until the LLM gives the final answer.

  The LLM never touches the database itself. It can only ask. Our code decides what runs.

RUN IT
  python agent.py "How many orders did we get from Mumbai last month?"
  python agent.py "What was our revenue last month?"              raw tables only
  python agent.py "What was our revenue last month?" --context    with the dbt definitions
  add --pause to stop after every step (press Enter to continue)
"""
import json
import os
import sys

import duckdb                      # the database: one file, no server needed
from dotenv import load_dotenv
from groq import Groq              # the Groq API (OpenAI-style chat + tool calling)

import show                        # only prints things nicely in the terminal, no logic in there


# ---------------------------------------------------------------------------
# 1. SETTINGS
# ---------------------------------------------------------------------------
QUESTION = sys.argv[1]
USE_CONTEXT = "--context" in sys.argv      # give the agent the data team's definitions?
load_dotenv()                              # picks up GROQ_API_KEY from .env
MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
TODAY = "2026-10-15"                       # fixed, so "last month" always means September 2026
FOLDER = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# 2. CONNECT TO THE WAREHOUSE  (read-only, so the agent can never change any data)
# ---------------------------------------------------------------------------
if USE_CONTEXT:
    # analytics.duckdb is built by dbt. It has the clean, documented tables (fct_orders).
    # We also attach the raw warehouse, so the agent can still see everything.
    db = duckdb.connect(f"{FOLDER}/dbt_project/analytics.duckdb", read_only=True)
    db.execute(f"ATTACH '{FOLDER}/warehouse.duckdb' AS raw (READ_ONLY)")
else:
    # Only the raw tables, exactly as they came from the app. No documentation at all.
    db = duckdb.connect(f"{FOLDER}/warehouse.duckdb", read_only=True)

# The LLM writes the SQL, so block everything outside the database files: no reading or
# writing local files (read_csv, COPY TO), no URLs, no extension installs. Then lock the
# settings so a query cannot switch them back on.
db.execute("SET enable_external_access = false")
db.execute("SET lock_configuration = true")


def query_to_text(sql, max_rows=50):
    """Run a query and turn the result into a small text table that the LLM can read."""
    result = db.execute(sql)
    columns = [col[0] for col in result.description]
    rows = result.fetchmany(max_rows)
    lines = [" | ".join(columns)] + [" | ".join(str(value) for value in row) for row in rows]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 3. THE TOOLS  (normal Python functions. Each one returns text for the LLM to read.)
# ---------------------------------------------------------------------------
def list_tables():
    """LOOK: which tables exist?"""
    return query_to_text("SELECT database, schema, name FROM (SHOW ALL TABLES) "
                         "WHERE name NOT LIKE 'metricflow%'")


def describe_table(table):
    """LOOK: what columns does a table have? Plus 3 sample rows."""
    columns = query_to_text(f"SELECT column_name, column_type FROM (DESCRIBE {table})")
    sample = query_to_text(f"SELECT * FROM {table} LIMIT 3")
    return columns + "\n\nSample rows:\n" + sample


def run_sql(sql):
    """WRITE + RUN: run one SQL query and return up to 50 rows."""
    return query_to_text(sql)


def get_business_definitions():
    """LOOK: read the data team's dbt docs and metric definitions (only in --context mode)."""
    files = ["schema.yml", "semantic_models.yml"]
    return "\n\n".join(open(f"{FOLDER}/dbt_project/models/marts/{f}").read() for f in files)


# Tool name -> the Python function that runs it
TOOLS = {"list_tables": list_tables, "describe_table": describe_table, "run_sql": run_sql}
if USE_CONTEXT:
    TOOLS["get_business_definitions"] = get_business_definitions


# The same tools, described for the LLM: a name, what it does, and what inputs it takes.
def tool_spec(name, description, inputs=None):
    properties = {key: {"type": "string"} for key in (inputs or [])}
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties, "required": list(properties)}}}


TOOL_SPECS = [
    tool_spec("list_tables", "List every table in the warehouse."),
    tool_spec("describe_table", "Show the columns and 3 sample rows of one table.", ["table"]),
    tool_spec("run_sql", "Run one read-only DuckDB SQL query and get up to 50 rows back.", ["sql"]),
]
if USE_CONTEXT:
    TOOL_SPECS.append(tool_spec("get_business_definitions",
                                "Read the data team's documented models and metric definitions. "
                                "Read this before computing any business metric."))


# ---------------------------------------------------------------------------
# 4. THE INSTRUCTIONS  (the system prompt: who the agent is and how it should work)
# ---------------------------------------------------------------------------
INSTRUCTIONS = f"""You are a data analyst agent for a food delivery company in India. Today is {TODAY}.
You can only learn about the data through your tools. Work in a loop: plan, look at the tables
you need, write SQL, run it, then check if the result makes sense. If not, fix the SQL and run again.
When you are confident, give a short final answer: the number (Indian format, like 12,34,567),
one line on how you got it, and the final SQL in a sql code block."""

if USE_CONTEXT:
    INSTRUCTIONS += """
The data team documents its tables and metrics in dbt. Always read the business definitions first,
prefer the documented tables over raw ones, and follow the metric definitions exactly."""


# ---------------------------------------------------------------------------
# 5. THE AGENT LOOP
# ---------------------------------------------------------------------------
client = Groq(max_retries=8)                          # reads GROQ_API_KEY; retries rate limits (free tier: 8,000 tokens/min)
messages = [{"role": "system", "content": INSTRUCTIONS},     # the conversation so far
            {"role": "user", "content": QUESTION}]
show.start(QUESTION, USE_CONTEXT, TODAY)

for turn in range(15):                                # safety limit, so it can never loop forever

    # 5a. Ask the model what to do next
    response = client.chat.completions.create(model=MODEL, max_tokens=2000,
                                              tools=TOOL_SPECS, messages=messages)
    message = response.choices[0].message
    calls = message.tool_calls or []
    messages.append({"role": "assistant", "content": message.content or "",
                     "tool_calls": [{"id": c.id, "type": "function",
                                     "function": {"name": c.function.name, "arguments": c.function.arguments}}
                                    for c in calls] or None})

    # 5b. No tool requested? Then this is the final answer. Done.
    if not calls:
        show.answer(message.content)
        break

    # 5c. Run every tool the model asked for, and send each result back
    show.thinking(message.content or "", first_turn=(turn == 0))   # the model thinking out loud
    for call in calls:
        inputs = json.loads(call.function.arguments or "{}")
        show.tool_call(call.function.name, inputs)
        try:
            output = TOOLS[call.function.name](**inputs)
        except Exception as error:                    # bad SQL? Send the error back.
            output = f"ERROR: {error}"                # The agent reads it and fixes its own query.
        show.tool_result(call.function.name, output)
        messages.append({"role": "tool", "tool_call_id": call.id, "content": output})
    # ...then go round the loop again
