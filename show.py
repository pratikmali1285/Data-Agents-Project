"""
show.py  -  prints each step of the agent in a coloured box, so viewers can follow the loop.

There is no agent logic in this file. It only decides how things look on screen:
  PLAN   magenta  the LLM's first thoughts about the question
  LOOK   cyan     list_tables, describe_table, get_business_definitions
  WRITE  yellow   the SQL the LLM wrote
  RUN    green    the result of that SQL (red if it failed)
  CHECK  blue     the LLM looking at a result and deciding what to do next
  ANSWER white    the final answer
"""
import sys

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax

console = Console(width=110)
PAUSE = "--pause" in sys.argv          # wait for Enter after every box


def box(label, color, content):
    console.print(Panel(content, title=f"[bold {color}]{label}[/]", title_align="left", border_style=color))
    if PAUSE:
        input()


def start(question, use_context, today):
    mode = "raw tables + dbt definitions" if use_context else "raw tables only"
    console.rule(f"[bold]Data agent[/]  ·  {mode}  ·  today = {today}")
    console.print(f"[bold]Question:[/] {question}\n")


def thinking(text, first_turn):
    if text.strip():
        box("PLAN" if first_turn else "CHECK", "magenta" if first_turn else "blue", Markdown(text))


def tool_call(name, inputs):
    if name == "run_sql":
        box("WRITE", "yellow", Syntax(inputs["sql"].strip(), "sql", theme="monokai", word_wrap=True))
    else:
        args = ", ".join(str(v) for v in inputs.values())
        box("LOOK", "cyan", f"{name}({args})")


def tool_result(name, output):
    if output.startswith("ERROR"):
        box("RUN", "red", output)
    elif name == "run_sql":
        box("RUN", "green", output)
    else:
        lines = output.splitlines()
        box("LOOK", "cyan", "\n".join(lines[:30]) + ("\n..." if len(lines) > 30 else ""))


def answer(text):
    box("ANSWER", "white", Markdown(text))


def chatbot(question, text):
    console.rule("[bold]Plain chatbot[/]  ·  no tools, never sees your data")
    console.print(f"[bold]Question:[/] {question}\n")
    box("CHATBOT", "red", Markdown(text))
