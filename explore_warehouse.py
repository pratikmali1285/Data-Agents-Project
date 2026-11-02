"""
explore_warehouse.py  -  look inside warehouse.duckdb, the same way the agent will

RUN IT
  python explore_warehouse.py            every table: how many rows, and what one row means
  python explore_warehouse.py orders     one table: its columns and 5 sample rows
  python explore_warehouse.py traps      the 3 things that make "revenue" tricky, with real rows
  python explore_warehouse.py ui         open the DuckDB UI in your browser (read-only)
"""
import os
import sys

import duckdb
from rich.console import Console
from rich.table import Table

FOLDER = os.path.dirname(os.path.abspath(__file__))
DB_PATH = f"{FOLDER}/warehouse.duckdb"
console = Console(width=120)

# What one row of each table means, in plain words
TABLES = {
    "cities": "one city",
    "restaurants": "one restaurant (and which city it is in)",
    "customers": "one customer",
    "orders": "one order placed on the app",
    "order_taxes": "the GST charged on one order",
    "refunds": "one refunded order",
}


def show_query(db, sql, title=None):
    """Run a query and print the result as a table on screen."""
    result = db.execute(sql)
    table = Table(title=title, title_justify="left", header_style="bold cyan")
    for col in result.description:
        table.add_column(col[0])
    for row in result.fetchall():
        table.add_row(*[str(value) for value in row])
    console.print(table)


# ---------------------------------------------------------------------------
# 1. OVERVIEW: every table, its size, and how the tables connect
# ---------------------------------------------------------------------------
def overview(db):
    table = Table(title="warehouse.duckdb", title_justify="left", header_style="bold cyan")
    for col in ["table", "rows", "one row is", "columns"]:
        table.add_column(col)
    for name, meaning in TABLES.items():
        rows = db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        columns = [c[0] for c in db.execute(f"DESCRIBE {name}").fetchall()]
        table.add_row(name, f"{rows:,}", meaning, ", ".join(columns))
    console.print(table)

    console.print("""
[bold]How the tables connect[/]

   cities ──< restaurants ──< orders >── customers
                                │
                                ├── order_taxes   one row per order: the GST
                                └── refunds       only for orders that were refunded

   An order's city comes from its restaurant:  orders → restaurants → cities
""")


# ---------------------------------------------------------------------------
# 2. ONE TABLE: its columns and a few sample rows
# ---------------------------------------------------------------------------
def one_table(db, name):
    show_query(db, f"SELECT column_name, column_type FROM (DESCRIBE {name})", f"{name}: columns")
    show_query(db, f"SELECT * FROM {name} LIMIT 5", f"{name}: 5 sample rows")


# ---------------------------------------------------------------------------
# 3. THE TRAPS: why "SUM(amount)" is not revenue
# ---------------------------------------------------------------------------
def traps(db):
    console.print("\n[bold]Trap 1.[/] orders.amount = item value + GST, before the promo discount. "
                  "GST sits in another table.")
    show_query(db, """
        SELECT o.order_id, o.amount, o.promo_value, t.gst,
               o.amount - o.promo_value - t.gst AS what_we_actually_earn
        FROM orders o JOIN order_taxes t USING (order_id)
        WHERE o.promo_value > 0
        LIMIT 3""")

    console.print("\n[bold]Trap 2.[/] A refunded order still says 'delivered' in orders. "
                  "You only find out in the refunds table.")
    show_query(db, """
        SELECT o.order_id, o.status, o.amount, r.refund_amount, r.reason
        FROM orders o JOIN refunds r USING (order_id)
        LIMIT 3""")

    console.print("\n[bold]Trap 3.[/] Cancelled orders still have an amount, so they sneak into SUM(amount).")
    show_query(db, """
        SELECT status, COUNT(*) AS orders, SUM(amount) AS total_amount
        FROM orders
        WHERE order_ts >= '2026-09-01' AND order_ts < '2026-10-01'
        GROUP BY status ORDER BY orders DESC""", "September 2026")

    console.print("\nThe real rule (written only in dbt): revenue = delivered and not refunded orders, "
                  "after promo, without GST.\n")


# ---------------------------------------------------------------------------
# 4. THE DUCKDB UI: browse the tables and write SQL in your browser
# ---------------------------------------------------------------------------
def open_ui():
    # We attach the warehouse READ-ONLY, so the agent can still read it while the UI is open.
    # (Opening the file directly with "duckdb -ui warehouse.duckdb" would lock it.)
    db = duckdb.connect()
    db.execute(f"ATTACH '{DB_PATH}' AS warehouse (READ_ONLY)")
    db.execute("USE warehouse")
    db.execute("CALL start_ui()")
    console.print("DuckDB UI is running at [bold]http://localhost:4213[/]. Press Enter here to stop it.")
    input()


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else "overview"
    if choice == "ui":
        open_ui()
    else:
        db = duckdb.connect(DB_PATH, read_only=True)
        if choice == "overview":
            overview(db)
        elif choice == "traps":
            traps(db)
        elif choice in TABLES:
            one_table(db, choice)
        else:
            print(f"Unknown option '{choice}'. Use one of: overview, traps, ui, {', '.join(TABLES)}")
