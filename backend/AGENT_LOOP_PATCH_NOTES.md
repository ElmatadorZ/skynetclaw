# SkynetClaw Agent Loop — Anti-Cycle Patch

Date: 2026-04-30
File patched: `backend/main.py`
Function: `agent_run` + `GENESIS_AGENT_PROMPT`

## Problem

Local model (gemma2:27b / Genesis-Mind:latest) repeated identical tool calls
(`create_folder` + `write_file requirements.txt`) over and over without
progressing — classic agent-loop failure mode caused by:

1. No injected memory of completed actions
2. No cycle / duplicate detection
3. No explicit plan to track step N/total
4. System prompt did not forbid duplicate calls

## Fix Stack (applied in order)

### 1. System Prompt Hardening — `GENESIS_AGENT_PROMPT`
- New "ANTI-LOOP / IDEMPOTENCY RULE" section: model must scan
  COMPLETED_ACTIONS before every call, and skip duplicates.
- New "PLAN-FIRST RULE": on step 1, model must emit
  `PLAN: 1) ... | 2) ... | 3) ...` before the first tool call.
- L0 of Genesis Protocol now explicitly references COMPLETED_ACTIONS.

### 2. Action Signature Tracking
- `_action_sig(name, args)` produces a stable, normalized signature like
  `write_file(content=python-...|path=D:\...)`.
- Each successful call appends its signature to `action_sigs`.

### 3. Live Ledger Injection
- Before every step, a `system` message is rebuilt and appended:
  ```
  ## PLAN (from step 1): ...
  ## COMPLETED_ACTIONS (do NOT repeat):
    1. ✅ create_folder(path=D:\Skynet_Bridge)
    2. ✅ write_file(content=...|path=...\requirements.txt)
  ```
- The previous ledger is removed first, so we never accumulate
  context-window bloat — only the latest snapshot lives in `cur`.

### 4. Dedupe Guard (per tool call)
- If the model emits a tool call whose signature matches an already-completed
  action, the call is **blocked** before `exec_tool` runs.
- A synthetic tool result is injected: `⚠ DUPLICATE BLOCKED: ...`
- Frontend receives `agent_tool_skip` event so the UI can render it.

### 5. Cycle Breaker (3-strike rule)
- `recent_sigs` tracks the last 3 action signatures.
- If all 3 are identical, the loop **breaks immediately** with
  `agent_stuck` event (reason: cycle).

### 6. Stagnation Detector
- If a step has tool calls but none of them produce a NEW action (all blocked
  as duplicates), `no_progress_rounds` increments.
- 2 stagnant rounds in a row → break (reason: stagnation).

### 7. PLAN Capture
- The first time the model emits a `PLAN:` line, the line is parsed,
  trimmed to 600 chars, stored in `captured_plan`, and re-injected at the
  top of every ledger message thereafter.
- Frontend gets a new `agent_plan` event for nice UI rendering.

## Frontend events to optionally handle

| event              | new? | meaning                                     |
|--------------------|------|---------------------------------------------|
| `agent_plan`       | ✅   | model emitted its plan                      |
| `agent_tool_skip`  | ✅   | duplicate call was blocked                  |
| `agent_stuck`      | now has `reason: 'cycle' \| 'stagnation'`   |

Existing events (`agent_step`, `agent_tool_call`, `agent_tool_result`,
`agent_complete`, `agent_limit`, `done`) are unchanged.

## Backwards compatibility

- Public API (`/api/agent/run`) — unchanged signature.
- Memory format (`agent_memory.json`) — unchanged.
- Tool definitions (`BUILTIN_TOOLS`) — unchanged.
- Only behavior change: the agent now refuses to repeat itself.

## Test recipe

Restart backend (`restart_backend.bat`), then send the same task that
previously looped:

```
สร้าง Telegram Bot ที่ D:\Skynet_Bridge ทำให้เสร็จทั้งหมด
```

Expected on screen:
1. Step 1 → model emits `PLAN: 1) create folder | 2) write requirements.txt | 3) write bot.py | ...`
2. Each step the right-side log shows COMPLETED_ACTIONS growing.
3. If the model tries to repeat `write_file requirements.txt` → blocked,
   shown as a yellow `agent_tool_skip` line.
4. Run completes with `TASK_COMPLETE` or aborts cleanly with
   `agent_stuck (reason=cycle)` instead of looping forever.

## Recommended next upgrade

Switch model from gemma2:27b to a stronger tool-using local model:
- `qwen2.5-coder:32b`
- `qwen2.5:32b-instruct`
- `mistral-small3:24b`

The patch makes the loop safer regardless of model — but a stronger model
will hit `TASK_COMPLETE` instead of the cycle breaker.
