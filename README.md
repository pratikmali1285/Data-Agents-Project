# Data agent demo

A small, complete data agent you can run on your laptop and read in one sitting.
It is the live demo from the DataVidhya video "What is a data agent, and will it replace data engineers?"

Based on [darshilparmar/data-agent-demo](https://github.com/darshilparmar/data-agent-demo).

## What is a data agent?

A **data agent** is a large language model (LLM) that answers questions about your data by
**working with the data itself**, not by guessing from memory. You ask in plain English; the agent
looks at the warehouse, writes SQL, runs it, checks the result and replies with a number plus the
SQL that produced it.

It is three things working together:

| Part | Role | In this repo |
|---|---|---|
| **The brain** | An LLM that reads the question and decides the next step. It can only *ask* for actions. | the model called from `agent.py` |
| **The tools** | Small functions the LLM is allowed to request: list tables, describe a table, run SQL, read business definitions. | section 3 of `agent.py` |
| **The loop** | Our code: sends the question and tool list to the LLM, runs whatever tool it asks for, sends the result back, repeats. | section 5 of `agent.py` |

### Three types of data agents

| Type | What it does | Example |
|---|---|---|
| **Analyst agents** | Answer business questions from your warehouse. | "Mumbai orders in September?" → warehouse → **6,171** |
| **Engineering agents** | Write pipelines and dbt models, fix broken code. | Spots `status = 'deliverd'` in the `stg_orders → fct_orders` models and fixes it to `'delivered'` |
| **Ops agents** | Watch data quality and tell you when a pipeline fails, and why. | Runs quality checks such as `orders_daily` and `refunds_sync` and alerts when one stops passing |

This repo builds an **analyst agent**. The other two run the same loop with different tools
(edit a file, run dbt, read pipeline logs) instead of "run SQL".

**Chatbot vs data agent.** A chatbot gets only the question, so it can only guess (`chatbot.py`).
A data agent gets the question **plus tools and access to the data**, so it can look, try, see its
mistakes and fix them (`agent.py`).

### Three ways to ask the same question

| | 1 · Chatbot | 2 · Data agent | 3 · Agent + context |
|---|---|---|---|
| **Sees** | No data | The tables only (`orders`, `restaurants`, `cities`, …) | The tables **plus the business definitions** |
| **Run it** | `python chatbot.py "..."` | `python agent.py "..."` | `python agent.py "..." --context` |
| **"Why did Mumbai orders drop last week?"** | Invents a story (monsoon, festivals, competitors) | Finds the real cause in the data | Finds the real cause in the data |
| **"What was our revenue last month?"** | Cannot know | Valid SQL, wrong meaning (one real run: ₹88,00,241) | **₹78,09,309**, the company's own definition |

Each step adds something: the chatbot has **no data**, the agent sees **tables only**, and the
agent with context **knows the business**.

### How it works, step by step

1. **Ask.** You give a question, e.g. *"How many orders did we get from Mumbai last month?"*
2. **Plan.** The LLM receives the question, its instructions (the system prompt) and the list of tools.
   It decides what it needs to know first.
3. **Look.** It asks for `list_tables` / `describe_table` to learn which tables and columns exist.
4. **Write and run.** It writes SQL and asks for `run_sql`. Our code runs it on DuckDB, **read-only**,
   and sends back the rows (or the error message).
5. **Check.** The LLM reads the result. Wrong-looking number or SQL error? It fixes the query and runs
   it again.
6. **Answer.** When it is confident, it stops asking for tools and returns the answer, how it got it,
   and the final SQL. (A safety limit of 15 turns stops it from looping forever.)

### The loop in action: "Why did our orders drop in Mumbai last week?"

An agent actually *does things*. Here is what the loop looks like on the demo's drop question:

| Step | What the agent does | What it gets back |
|---|---|---|
| **01 · Plan** | Decides it needs Mumbai's order count per week. | |
| **02 · Look** | Finds the right data: city reaches an order through its restaurant (`orders → restaurants → cities`, joined on `restaurant_id` and `city_id`). | table and column names |
| **03 · Write** | Turns the question into a query: `SELECT week, COUNT(*) ... WHERE c.city_name = 'Mumbai' GROUP BY week` | |
| **04 · Run + read** | Runs it (under a second, 2 rows back). | 1,422 → 1,311 orders, only −8% |
| **05 · Check** | *"Does this make sense?"* No: `COUNT(*)` **counts cancelled orders too**, so the drop is hidden. | |
| **↺ Retry** | Something looks wrong, so it tries again: changes "any status" to `status = 'delivered'` (and not refunded). | **1,208 → 816 delivered, −32%**; cancellations 131 → 438 |
| **Answer** | Delivered orders fell 32% because cancellations tripled, mostly `heavy_rain_no_rider`. | number + method + SQL |

The Check step is what separates an agent from a SQL generator. A query that runs without error
can still answer the wrong question.

The LLM never touches the database. It can only request a tool; our code decides what actually runs.

**Its weak spot is meaning, not SQL.** The agent can write correct SQL and still give the wrong answer
if it does not know the business rules (for example, what counts as "revenue"). Give it the data
team's documented definitions (`--context`, from `dbt_project/`) and it follows them instead of guessing.

## The big picture

```
   You ask a question
          │
          ▼
   ┌──────────────┐   "run this SQL"    ┌──────────────┐   SQL    ┌────────────────────┐
   │   agent.py   │ ◀────────────────── │   Groq LLM   │          │  warehouse.duckdb  │
   │  (our code)  │ ──────────────────▶ │  (the brain) │          │   (the raw data)   │
   └──────────────┘   the result        └──────────────┘          └────────────────────┘
          │                                                                 ▲
          └───────────── our code runs the SQL on DuckDB, read-only ───────┘

   Repeat until the LLM has the answer:  PLAN → LOOK → WRITE → RUN → CHECK → ANSWER
```

- **The Groq LLM** (`openai/gpt-oss-120b` by default) decides what to do next. It never touches the data itself.
- **agent.py** is the middleman. It gives the LLM a few tools, runs whatever tool the LLM
  asks for, and sends the result back.
- **DuckDB** is the warehouse. One file, no server, opened read-only.

## Read the files in this order

| # | File | What it is | Explain it as |
|---|---|---|---|
| 1 | `warehouse.duckdb` + `explore_warehouse.py` | The data: a fake food delivery company. 6 tables, 1.7 lakh orders. The script shows you what is inside. | "This is our company's warehouse. Let's look inside." |
| 2 | `chatbot.py` | About 30 lines. Sends the question to the Groq LLM with no tools and no data. | "A chatbot can only guess." |
| 3 | `agent.py` | About 100 lines of real code in 5 sections: settings, connect, tools, instructions, loop. | "An agent can look, run SQL and check." |
| 4 | `show.py` | Only the coloured boxes on screen. No logic. Skip it on camera. | "This just makes it pretty." |
| 5 | `dbt_project/` | The data team's work: clean tables, docs, tests and metric definitions. | "This is the context the agent was missing." |
| 6 | `answers.sql` + `check_answers.py` | The correct SQL for every question, to check the agent. | "Never trust the agent blindly." |
| – | `build_warehouse.py` | Generates the fake data. Commented, but you never need to run it. | "Just a data generator." |
| – | `mcp/` | The no-code version: Claude Desktop connected to the same file through MCP. | "Same idea, no code." |

## The tables

| Table | One row per | Watch out |
|---|---|---|
| `cities` | city | |
| `restaurants` | restaurant | has a `city_id`, so city comes through here |
| `customers` | customer | |
| `orders` | order | `amount` includes GST and is before the promo. A refunded order still says `delivered`. |
| `order_taxes` | order | the GST for each order |
| `refunds` | refunded order | |

**Revenue** at this company = delivered and not refunded orders, after promo discount, without GST.
That rule is not written anywhere in these tables. It only exists in `dbt_project/`. That is the whole point of the demo.

## Look at the database

Before the agent touches the data, look at it yourself. Three ways, pick one.

**1. In the terminal (easiest)**

```bash
python explore_warehouse.py            # every table: rows, columns, what one row means, how they connect
python explore_warehouse.py orders     # one table: columns + 5 sample rows (any table name works)
python explore_warehouse.py traps      # the 3 traps that make "revenue" tricky, shown with real rows
```

**2. In your browser, with the DuckDB UI**

```bash
python explore_warehouse.py ui         # then open http://localhost:4213
```

You get a table browser on the left and a SQL notebook on the right. Click `warehouse` → `main`
to see the tables, or write SQL in a cell, for example:

```sql
SELECT status, COUNT(*) FROM orders GROUP BY status;
```

The script opens the warehouse read-only, so you can keep the UI open while the agent runs.
The UI downloads its web files from ui.duckdb.org the first time, so you need internet. Press
Enter in the terminal to stop it. (Avoid `duckdb -ui warehouse.duckdb`: that locks the file and
the agent can no longer open it.)

**3. With the DuckDB command line** (install with `brew install duckdb`)

```bash
duckdb -readonly warehouse.duckdb
```
```sql
SHOW TABLES;              -- list the tables
DESCRIBE orders;          -- columns and types
SUMMARIZE orders;         -- min, max, nulls and distinct values for every column
FROM orders LIMIT 5;      -- a few rows
.quit
```

## Run it

```bash
# one time
python3 -m venv .venv && source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip3 install -r requirements.txt
export GROQ_API_KEY=gsk_...                              # Windows: set GROQ_API_KEY=...  (or put it in .env)

# 1. chatbot vs agent
python chatbot.py "Why did our orders drop in Mumbai last week?"
python agent.py   "Why did our orders drop in Mumbai last week?"

# 2. the agent gets it right
python agent.py "How many orders did we get from Mumbai last month?"         # correct: 6,171

# 3. the agent gets it wrong
python agent.py "What was our revenue last month?"                           # correct: ₹78,09,309

# 4. the fix: give it the data team's definitions
pip install -r requirements-dbt.txt
cd dbt_project && dbt build --profiles-dir . && cd ..
python agent.py "What was our revenue last month?" --context

# check any number yourself
python check_answers.py
```

Add `--pause` to any `agent.py` command to stop after every step while you explain it.

The agent's "today" is fixed at 15 Oct 2026, so "last month" is always September 2026 and
"last week" is always 5 to 11 Oct 2026. The default model is `openai/gpt-oss-120b` on Groq;
change it with `GROQ_MODEL=...`.

## The dbt project in one minute

```
raw tables (warehouse.duckdb)
   │  sources.yml           tells dbt where the raw tables are
   ▼
staging                     stg_orders: rename columns, bring in GST and refunds
   │                        stg_restaurants: add the city name
   ▼
marts                       fct_orders: one row per order, with net_revenue = the business rule
   │  schema.yml            descriptions + tests (the agent reads these in --context mode)
   ▼
semantic layer              semantic_models.yml: revenue, orders, cancellation rate... defined once
```

Query a metric straight from the semantic layer:

```bash
cd dbt_project
export DBT_PROFILES_DIR=.
mf query --metrics revenue --group-by metric_time__month --start-time 2026-09-01 --end-time 2026-09-30
```

All data is synthetic, generated with a fixed seed. Names and numbers are not real.
