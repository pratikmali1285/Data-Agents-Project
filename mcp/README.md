# No-code version: Claude Desktop + MCP

This connects Claude Desktop straight to `warehouse.duckdb`, read-only, with the
official DuckDB / MotherDuck MCP server. No Python needed.

1. Install `uv` (https://docs.astral.sh/uv/). It gives you `uvx`.
2. Open Claude Desktop, Settings, Developer, Edit Config.
3. Paste the contents of `claude_desktop_config.json` and change the path to the real
   absolute path of `warehouse.duckdb` on your machine.
4. Restart Claude Desktop. You should see the tools `list_tables`, `list_columns`
   and `execute_query`.
5. Ask the same questions as the terminal demo.

Read-only is the default for this server. If you see `spawn uvx ENOENT`, put the full
path from `which uvx` in "command".

To show "the fix" here: add the text of `dbt_project/models/marts/schema.yml` and
`semantic_models.yml` to the chat (or a Claude Project's knowledge) and ask the revenue
question again.
