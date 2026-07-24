# TOOLS — Catalog & Routing

Skills define _how_ tools work. This file is the agent's cheat-sheet — when to reach for which tool.

## Tool families (33 built-in)

### File system (read/write)

- `read_file(path)` — read any file
- `write_file(path, content)` — write/overwrite (Shadow Gate intercepts for live-data check)
- `edit_file(path, old_text, new_text)` — surgical text replace
- `delete_file(path, recursive=false)` — irreversible — Shadow Gate confirms on system folders
- `move_file(source, destination)` / `copy_file(source, destination)`
- `create_folder(path)` — idempotent
- `list_files(path)` / `find_files(path, pattern)` / `file_info(path)`

### Code execution

- `run_python(code)` — sandbox-y; for scripts, calculations
- `shell_command(command, cwd?, timeout=30)` — full shell; Shadow Gate denylists `rm -rf /`, `format`, `shutdown`, etc.
- `install_package(package, manager=pip|npm|winget|choco|cargo)`

### System

- `get_system_info()` / `list_processes(filter)` / `kill_process(pid|name)`
- `take_screenshot(path?)` / `open_browser(url)`
- `clipboard_read()` / `clipboard_write(text)`

### Real-time data (call FIRST before writing files with live values)

- `get_current_datetime(timezone="Asia/Bangkok")` — but datetime is auto-injected; call only if user wants fresh server time mid-session
- `get_gold_price(currency)` — multi-source: CoinGecko PAXG + GoldPrice.org + Stooq + Yahoo + Thai GTA chnwt.dev
- `get_crypto_price(symbols, vs_currency)` — multi-source: CoinGecko + Binance + Coinbase
- `get_forex_rate(base, targets)` — multi-source: Yahoo + open.er-api + frankfurter
- `get_news(topic, max_results)` — DuckDuckGo Lite

### Web

- `web_search(query, max_results)` — DuckDuckGo Lite + Bing fallback
- `http_request(url, method=GET, headers, body, params)` — generic HTTP
- `download_file(url, destination)`

### Obsidian

- `search_obsidian(query, top_k)` — vault search
- `read_obsidian_note(name)` / `write_obsidian_note(name, content, folder)`

### Social / messaging

- `telegram_send(message, chat_id?)` / `discord_send(message, channel?)` / `line_notify(message)` / `facebook_post(message, page_id)`
- `call_integration(integration_name, method, endpoint, body)` — generic webhook caller
- All outbound messaging requires Shadow Gate confirmation (irreversible)

### Elicitation

- `ask_user_options(question, options[4-5], allow_custom?, context?)` — halts the loop, waits for user reply

## Intent → tool routing

| User says ...                                | Use this tool first                           |
|----------------------------------------------|-----------------------------------------------|
| read/explore Obsidian                        | `search_obsidian`; if no vault → `list_files` |
| about files/folders                          | `list_files` / `find_files` / `read_file`     |
| create / build / save                        | `write_file` (always tool, never paste text)  |
| live prices / forex / news                   | `get_*` tools — NEVER training data           |
| general web question                         | `web_search` with concise keywords            |
| run a calculation                            | `run_python`                                  |
| check what's installed                       | `list_processes` / `get_system_info`          |

## Forbidden phrases

You ALWAYS have a tool — try it first:

- ❌ "I cannot access files" → wrong, use `read_file`
- ❌ "I cannot open Obsidian" → wrong, use `search_obsidian` (fallback `list_files`)
- ❌ "You need to paste the content" → wrong, fetch it yourself
- ❌ "ราคาทองล่าสุดคือ ~$2,000" → wrong, call `get_gold_price` first

## File writing rule (CRITICAL)

- To create a file: use `write_file` tool with FULL content in the `content` parameter.
- NEVER write "Here is the code:" followed by a code block — that causes stream abort.
- NEVER display file content in text — always pass it directly to `write_file`.
- One `write_file` call per file.
- Do NOT rewrite a file that already exists in COMPLETED_ACTIONS unless its content needs to change.
