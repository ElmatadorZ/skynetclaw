"""
builtin_tools.py — the built-in tool schemas (BUILTIN_TOOLS)
===========================================================
Extracted from main.py — God Object decomposition, strangler-fig slice 4. The base
list of tool JSON schemas (pure data). main imports this list, then extends it
in-place with the Obsidian tools and rebinds it with the stealth-browser tools (that
wiring stays in main because it depends on obsidian_tools / stealth_bridge). Every
reader (main, eval_suite, system_graph) sees main.BUILTIN_TOOLS unchanged.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

BUILTIN_TOOLS = [
    # ── File System ──
    {"type":"function","function":{"name":"read_file","description":"Read a local file. Large files are auto-truncated — pass offset (1-based start line) and limit (max lines) to read a specific region. Use grep_search FIRST to find which lines matter.",
        "parameters":{"type":"object","properties":{"path":{"type":"string"},"offset":{"type":"integer","default":1,"description":"1-based start line"},"limit":{"type":"integer","default":0,"description":"max lines (0 = auto)"},"line_numbers":{"type":"boolean","default":False,"description":"prefix each line with its number (do NOT copy prefixes into edit_file old_text)"}},"required":["path"]}}},
    {"type":"function","function":{"name":"write_file","description":"Write/overwrite content to a file",
        "parameters":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}}},
    {"type":"function","function":{"name":"edit_file","description":"Edit a file by replacing old text with new text. By default replaces FIRST occurrence only — set replace_all=true to replace every occurrence.",
        "parameters":{"type":"object","properties":{"path":{"type":"string"},"old_text":{"type":"string"},"new_text":{"type":"string"},"replace_all":{"type":"boolean","default":False}},"required":["path","old_text","new_text"]}}},
    {"type":"function","function":{"name":"delete_file","description":"Delete a file or empty folder. Use recursive=true for non-empty folders",
        "parameters":{"type":"object","properties":{"path":{"type":"string"},"recursive":{"type":"boolean","default":False}},"required":["path"]}}},
    {"type":"function","function":{"name":"move_file","description":"Move or rename a file/folder",
        "parameters":{"type":"object","properties":{"source":{"type":"string"},"destination":{"type":"string"}},"required":["source","destination"]}}},
    {"type":"function","function":{"name":"copy_file","description":"Copy a file or folder",
        "parameters":{"type":"object","properties":{"source":{"type":"string"},"destination":{"type":"string"}},"required":["source","destination"]}}},
    {"type":"function","function":{"name":"create_folder","description":"Create a directory (and parents)",
        "parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
    {"type":"function","function":{"name":"list_files","description":"List files in a directory",
        "parameters":{"type":"object","properties":{"path":{"type":"string"},"show_hidden":{"type":"boolean","default":False}},"required":["path"]}}},
    {"type":"function","function":{"name":"find_files","description":"Find files matching a glob pattern recursively",
        "parameters":{"type":"object","properties":{"path":{"type":"string"},"pattern":{"type":"string"},"recursive":{"type":"boolean","default":True}},"required":["path","pattern"]}}},
    {"type":"function","function":{"name":"grep_search","description":"Search INSIDE files for a regex or plain text. Returns file:line: matched-line. THE tool for locating code/config/text before read_file or edit_file — never read whole big files to find something.",
        "parameters":{"type":"object","properties":{"pattern":{"type":"string","description":"regex (falls back to literal if invalid)"},"path":{"type":"string","default":".","description":"file or directory to search"},"glob":{"type":"string","default":"*","description":"filename filter e.g. *.py, *.html"},"max_results":{"type":"integer","default":50},"context":{"type":"integer","default":0,"description":"lines of context around each match (max 5)"}},"required":["pattern"]}}},
    {"type":"function","function":{"name":"file_info","description":"Get file metadata: size, dates, permissions",
        "parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
    # ── Code & Shell ──
    {"type":"function","function":{"name":"shell_command","description":"Execute a shell/cmd command on the system",
        "parameters":{"type":"object","properties":{"command":{"type":"string"},"cwd":{"type":"string"},"timeout":{"type":"integer","default":30}},"required":["command"]}}},
    {"type":"function","function":{"name":"run_python","description":"Execute Python code and return output",
        "parameters":{"type":"object","properties":{"code":{"type":"string"},"timeout":{"type":"integer","default":60,"description":"max seconds before kill (capped at 300)"}},"required":["code"]}}},
    {"type":"function","function":{"name":"calculator","description":"Compute a math expression EXACTLY and deterministically. ALWAYS use this for arithmetic instead of calculating in your head — never write a number you did not compute. Supports + - * / // % ** , parentheses, and functions sqrt abs round floor ceil exp log log10 log2 sin cos tan min max pow factorial gcd hypot degrees radians, and constants pi e tau. Thousands separators like 1,200 are fine. For a percentage write p/100*base (e.g. 10% of 500 → 10/100*500). Lighter and faster than run_python for numbers.",
        "parameters":{"type":"object","properties":{"expression":{"type":"string","description":"e.g. '1200*5', '(3+4.5)/2', 'sqrt(144)', '10/100*500'"}},"required":["expression"]}}},
    {"type":"function","function":{"name":"analyze_image","description":"LOOK at an image file and answer a question about it — OCR/read text, describe the scene, read a chart or screenshot, identify objects/colors/layout. Runs a LOCAL multimodal model (fully offline). Pass an image path (a file from take_screenshot works directly) and optionally what to ask. Use this whenever the task involves an image, screenshot, photo, diagram, or 'ดูรูป/อ่านรูป'.",
        "parameters":{"type":"object","properties":{"path":{"type":"string","description":"image file path (png/jpg/webp/…)"},"question":{"type":"string","default":"Describe this image in detail.","description":"what to ask about the image"}},"required":["path"]}}},
    {"type":"function","function":{"name":"install_package","description":"Install a software package. manager: pip|npm|winget|choco|cargo",
        "parameters":{"type":"object","properties":{"package":{"type":"string"},"manager":{"type":"string","default":"pip"}},"required":["package"]}}},
    {"type":"function","function":{"name":"dev_server","description":"Manage long-running BACKGROUND processes (dev servers): e.g. 'npm run dev', 'python -m http.server 8080', 'node server.js'. Never use shell_command for servers — it blocks then kills them. action=start launches and returns the first output; logs tails recent output; stop kills the process tree; list shows all running. Verification loop for web work: start → http_request the local URL → read logs for errors → fix files → re-check.",
        "parameters":{"type":"object","properties":{"action":{"type":"string","enum":["start","logs","stop","list"],"default":"start"},"command":{"type":"string","description":"shell command (required for action=start)"},"cwd":{"type":"string","description":"working dir (defaults to active workspace)"},"id":{"type":"string","description":"server id returned by start (for logs/stop)"},"lines":{"type":"integer","default":60,"description":"how many log lines to tail"}}}}},
    # ── System ──
    {"type":"function","function":{"name":"system_diagnostics","description":"Diagnose a computer problem with READ-ONLY system checks — Wi-Fi, network, drivers, disk, battery, GPU. Use THIS (not shell_command, not ask_user_options) to actually LOOK at the machine when the user reports a problem like 'wifi ต่อไม่ได้' / 'internet ช้า' / 'ไดรเวอร์'. Give a free-text `problem` to auto-pick a playbook, OR explicit `checks`. It never changes state, so run it immediately without asking. After diagnosing, if a repair is needed, use system_repair(list=true) to see the menu then propose ONE — the operator approves it.",
        "parameters":{"type":"object","properties":{"problem":{"type":"string","description":"the problem in the user's words, e.g. 'wifi ต่อไม่ได้'"},"checks":{"type":"array","items":{"type":"string"},"description":"explicit check keys (optional): wifi_status, wifi_drivers, ip_config, connections, drivers, disk, battery, gpu, system_info ..."}}}}},
    {"type":"function","function":{"name":"system_repair","description":"Run ONE curated, named REPAIR after diagnosis — flush_dns, renew_ip, register_dns, reset_winsock, reset_tcpip, restart_wifi. This CHANGES system state, so it requires the operator's approval at the gate. First call with list=true to see the menu, then propose the single best repair by name and explain why. Never guess — pick from the allowlist; you cannot write a raw command here.",
        "parameters":{"type":"object","properties":{"repair":{"type":"string","description":"repair name from the allowlist (flush_dns, renew_ip, reset_winsock, reset_tcpip, restart_wifi, register_dns)"},"list":{"type":"boolean","description":"true → just return the repair menu (read-only, no approval needed)"}}}}},
    {"type":"function","function":{"name":"get_system_info","description":"Get system info: OS, disk, memory, CPU",
        "parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"list_processes","description":"List running processes, optionally filtered by name",
        "parameters":{"type":"object","properties":{"filter":{"type":"string","default":""}}}}},
    {"type":"function","function":{"name":"kill_process","description":"Kill a process by PID or name",
        "parameters":{"type":"object","properties":{"pid":{"type":"integer"},"name":{"type":"string"}}}}},
    {"type":"function","function":{"name":"take_screenshot","description":"Capture the screen and save as PNG",
        "parameters":{"type":"object","properties":{"path":{"type":"string","default":""}}}}},
    {"type":"function","function":{"name":"open_browser","description":"Open a URL in the default browser",
        "parameters":{"type":"object","properties":{"url":{"type":"string"}},"required":["url"]}}},
    {"type":"function","function":{"name":"clipboard_read","description":"Read current clipboard text content",
        "parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"clipboard_write","description":"Write text to the clipboard",
        "parameters":{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}}},
    # ── Skill Discovery (Capability-Skill Architecture) ──
    {"type":"function","function":{"name":"find_skill","description":"Search the House's local skill registry for a playbook matching a task you have NOT done before or are unsure how to do well (design, debugging, discovery, planning, ...). Bilingual (th/en). Returns ranked skill names + descriptions + capabilities — then call use_skill(name) to load the best one. ALWAYS try this before improvising on unfamiliar specialised work.",
        "parameters":{"type":"object","properties":{"query":{"type":"string","description":"what you need help doing, e.g. 'ออกแบบ dashboard ให้สวย', 'debug stack trace', 'find OCR library'"},"top_k":{"type":"integer","default":5}},"required":["query"]}}},
    {"type":"function","function":{"name":"use_skill","description":"Load the FULL playbook of one skill by exact name (from find_skill results) into this conversation, then follow it for the current task.",
        "parameters":{"type":"object","properties":{"name":{"type":"string","description":"exact skill name, e.g. 'frontend-design'"}},"required":["name"]}}},
    # ── Real-time Data ──
    {"type":"function","function":{"name":"get_current_datetime","description":"Get the current date, time, day of week and timezone — always accurate, never outdated",
        "parameters":{"type":"object","properties":{"timezone":{"type":"string","default":"Asia/Bangkok","description":"IANA timezone e.g. Asia/Bangkok, UTC, America/New_York"}}}}},
    {"type":"function","function":{"name":"get_crypto_price","description":"Get real-time cryptocurrency prices from CoinGecko. Use this for BTC, ETH, BNB, SOL, XRP and any crypto price",
        "parameters":{"type":"object","properties":{"symbols":{"type":"string","description":"Comma-separated coin ids or symbols e.g. 'bitcoin,ethereum,solana' or 'BTC,ETH'"},"vs_currency":{"type":"string","default":"usd","description":"Quote currency: usd, thb, eur, etc."}},"required":["symbols"]}}},
    {"type":"function","function":{"name":"get_gold_price","description":"Get current gold price — returns BOTH USD spot (XAU/USD) and Thai gold (GTA baht) in one report. Takes no arguments. Always call this for gold price questions — never use training data.",
        "parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"get_forex_rate","description":"Get live foreign exchange rates. Use for USD/THB, EUR/USD, JPY/THB and all forex pairs.",
        "parameters":{"type":"object","properties":{"base":{"type":"string","default":"USD","description":"Base currency e.g. USD, EUR, THB"},"targets":{"type":"string","default":"THB,EUR,JPY,GBP,CNY,SGD,AUD,KRW","description":"Comma-separated target currencies"}}}}},
    {"type":"function","function":{"name":"get_news","description":"Get latest REAL news headlines (ranked, recent, from major outlets via Google News) on any topic. BEST tool for current events / market / financial / breaking news — prefer this over web_search for news. Returns title, source, date, link per item. Call multiple times with different topics to cover a theme.",
        "parameters":{"type":"object","properties":{"topic":{"type":"string","description":"Specific news topic/keywords, e.g. 'ราคาทองคำ', 'bitcoin price', 'ข่าวเศรษฐกิจไทย', 'AI agent 2026'"},"max_results":{"type":"integer","default":6},"lang":{"type":"string","description":"'th' (default, Thai sources) or 'en' (global English sources)"}},"required":["topic"]}}},
    {"type":"function","function":{"name":"read_document","description":"Extract readable text from a document or image FILE — PDF, DOCX, XLSX, HTML, CSV, TXT, code, or image. USE THIS to read any uploaded file / document the user gives you (the model is text-only, so this turns binary docs into text). Returns the extracted text.",
        "parameters":{"type":"object","properties":{"path":{"type":"string","description":"Absolute path to the file (e.g. an uploaded PDF/DOCX in the workspace)"}},"required":["path"]}}},
    {"type":"function","function":{"name":"build_news_report","description":"Build a COMPLETE news-report HTML file from real, importance-ranked news in ONE call. Give it topics; it fetches real headlines (Google News, major outlets), ranks by source authority + recency, de-dupes, and writes a clean linked HTML file to the workspace. USE THIS for any 'gather news / make a news dashboard / news summary / สรุปข่าว' request — it is deterministic and reliable. Do NOT hand-write the HTML yourself.",
        "parameters":{"type":"object","properties":{"topics":{"type":"array","items":{"type":"string"},"description":"News topics/keywords, e.g. ['ราคาทองคำ','bitcoin','ข่าวเศรษฐกิจไทย','หุ้นไทย']"},"title":{"type":"string","description":"Report title (e.g. 'สรุปข่าวการเงินสำคัญ')"},"filename":{"type":"string","description":"Output .html filename, lands in workspace","default":"news_report.html"},"per_topic":{"type":"integer","default":6},"lang":{"type":"string","default":"th"}},"required":["topics"]}}},
    # ── Network & Web ──
    {"type":"function","function":{"name":"web_search","description":"Search the web via DuckDuckGo for any query",
        "parameters":{"type":"object","properties":{"query":{"type":"string"},"max_results":{"type":"integer","default":5}},"required":["query"]}}},
    {"type":"function","function":{"name":"http_request","description":"Make HTTP request to any URL or API",
        "parameters":{"type":"object","properties":{"url":{"type":"string"},"method":{"type":"string","default":"GET"},"headers":{"type":"object"},"body":{"type":"object"},"params":{"type":"object"}},"required":["url"]}}},
    {"type":"function","function":{"name":"download_file","description":"Download a file from a URL to local disk",
        "parameters":{"type":"object","properties":{"url":{"type":"string"},"destination":{"type":"string","default":""}},"required":["url"]}}},
    # ── Obsidian ──
    {"type":"function","function":{"name":"search_obsidian","description":"Search Obsidian vault notes",
        "parameters":{"type":"object","properties":{"query":{"type":"string"},"top_k":{"type":"integer","default":5}},"required":["query"]}}},
    {"type":"function","function":{"name":"read_obsidian_note","description":"Read full content of an Obsidian note by name",
        "parameters":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}}},
    {"type":"function","function":{"name":"write_obsidian_note","description":"Create or update an Obsidian note",
        "parameters":{"type":"object","properties":{"name":{"type":"string"},"content":{"type":"string"},"folder":{"type":"string","default":""}},"required":["name","content"]}}},
    # ── Discovery (OX-1) — INVESTIGATE the House's own records before assuming/planning (read-only) ──
    {"type":"function","function":{"name":"query_missions","description":"DISCOVER FIRST: list the House's own missions — active/paused/completed/failed with confidence, health and next action. Use this BEFORE planning when asked about pending/outstanding work or status.",
        "parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"read_house_mind","description":"DISCOVER FIRST: the House's current cognitive state — objective, belief, confidence, known facts, unknowns, risks, hypotheses. Use this to answer 'what do we believe / what are we working on'.",
        "parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"query_timeline","description":"DISCOVER FIRST: recent belief evolution / what changed / what happened. Use for history and checkpoint questions.",
        "parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"query_learning","description":"DISCOVER FIRST: institutional lessons, repeat failures/successes, behavior changes. Use for 'what did we learn / what failed'.",
        "parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"recall_archive","description":"DISCOVER FIRST: prior deliberations and similar past missions for a directive — avoid redoing solved work.",
        "parameters":{"type":"object","properties":{"query":{"type":"string","description":"the directive to find similar prior work for"}}}}},
    # ── Epistemic self-audit — check the warrant BEFORE relying on a belief ──
    {"type":"function","function":{"name":"prove_it","description":"CHECK WARRANT BEFORE ASSERTING: the receipt for a belief — which agent asserted it, on what evidence, who dissented and whether that was ever resolved, what would prove it wrong, whether reality has graded it, and the calibrated track record of the asserters. Returns trust_basis EARNED or UNEARNED. Use before stating anything as established, and when the operator asks 'why do you believe that' or 'ตรวจสอบว่าเชื่อได้ไหม'.",
        "parameters":{"type":"object","properties":{"claim":{"type":"string","description":"the claim or topic to pull the record for"},"limit":{"type":"integer","description":"max items per section (default 6)"}},"required":["claim"]}}},
    {"type":"function","function":{"name":"self_audit","description":"The House's epistemic vital signs stated against itself: how many dissents were ever resolved, how many staked claims were graded, how many beliefs changed because of an outcome rather than more talk, how many agents have a real track record. Reports uncomfortable findings deliberately. Use when asked how reliable the House is, or before claiming the learning loop works.",
        "parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"pending_judgments","description":"What the learning loop is still waiting on, and WHO it is waiting on — separates claims whose horizon has not elapsed (reality has not answered) from claims that are overdue with no automatic judge (a human must rule, and until they do it blocks that session's dissents). Also flags malformed records. Use when asked what is outstanding, why a dissent is unresolved, or ทำไม loop ยังไม่ปิด.",
        "parameters":{"type":"object","properties":{"limit":{"type":"integer","description":"max items (default 20)"}}}}},
    # ── Social / Integrations ──
    {"type":"function","function":{"name":"telegram_send","description":"Send a message via Telegram bot (requires Telegram integration)",
        "parameters":{"type":"object","properties":{"message":{"type":"string"},"chat_id":{"type":"string","default":""}},"required":["message"]}}},
    {"type":"function","function":{"name":"discord_send","description":"Send a message to Discord (requires Discord integration)",
        "parameters":{"type":"object","properties":{"message":{"type":"string"},"channel":{"type":"string","default":""}},"required":["message"]}}},
    {"type":"function","function":{"name":"line_notify","description":"Send a Line Notify message (requires Line integration)",
        "parameters":{"type":"object","properties":{"message":{"type":"string"}},"required":["message"]}}},
    {"type":"function","function":{"name":"facebook_post","description":"Post to Facebook page (requires Facebook integration)",
        "parameters":{"type":"object","properties":{"message":{"type":"string"},"page_id":{"type":"string","default":"me"}},"required":["message"]}}},
    {"type":"function","function":{"name":"call_integration","description":"Call any saved custom integration by name",
        "parameters":{"type":"object","properties":{"integration_name":{"type":"string"},"method":{"type":"string","default":"GET"},"endpoint":{"type":"string","default":""},"body":{"type":"object"}},"required":["integration_name"]}}},
    # ── Elicitation (ask user back) ──
    {"type":"function","function":{"name":"ask_user_options",
        "description":(
            "Ask the user a clarification question with 4-5 multiple-choice options. "
            "Use this BEFORE acting when (a) the user's prompt is ambiguous and has more "
            "than one reasonable interpretation, (b) you are missing critical info needed "
            "to complete the task (file path, format, scope, target audience, etc.), or "
            "(c) a meaningful trade-off requires the user's preference. "
            "Do NOT use this for trivial choices you can decide yourself or for info "
            "available via other tools (use list_files / read_file first if relevant). "
            "After calling this tool, the conversation halts and waits for the user to "
            "click an option. The next user message will contain their choice."
        ),
        "parameters":{
            "type":"object",
            "properties":{
                "question":{"type":"string","description":"The clarification question, in the user's language. Be concise (1-2 sentences)."},
                "options":{"type":"array","items":{"type":"string"},"description":"4 to 5 short option strings (max ~80 chars each). Each option must be a complete, actionable answer."},
                "allow_custom":{"type":"boolean","default":True,"description":"Whether the user can also type a custom answer. Default true."},
                "context":{"type":"string","description":"(Optional) brief reason WHY you need to ask, shown to the user as a small hint."}
            },
            "required":["question","options"]
        }}},
]
