# Capability-Skill Architecture (CSA v1)

> Strangler-fig replacement for keyword auto-injection (`skills_auto_router`).
> Skills stop being prompt blobs matched by bag-of-words; they become assets
> **bound to Capabilities**, resolved by the architecture, and discoverable at
> runtime by the agent itself.

## Why (root causes of "skills don't help")

| # | Failure | Evidence |
|---|---------|----------|
| 1 | Imported skills carry auto-generated garbage triggers ("don", "like", "ask") | `find-skills/SKILL.md`, `frontend-design/SKILL.md` frontmatter |
| 2 | Design skills had **zero Thai triggers** — Thai briefs never activated them | DCA dashboard run 2026-07-18: plain default-styled page shipped |
| 3 | Injection is truncated (6k chars) and *discretionary* — context budget sheds skill messages first under the 16k ceiling | `main.py` `_discretionary_ids` + `context_budget` |
| 4 | No runtime discovery: once a run starts, the agent cannot ask "is there a skill for this?" | no `find_skill` tool in `BUILTIN_TOOLS` |

## Model

Per the Capability-first principle (Capability → Service → Engine → Tool → Validator):

```
Task (user text, th/en)
  │  resolve()            capability taxonomy — bilingual weighted keywords
  ▼
Capabilities              e.g. design.frontend, design.dashboard, discovery.search
  │  bind()               SKILL.md frontmatter `capabilities:` + DEFAULT_BINDINGS
  ▼
Skills (ranked)           trust-weighted via skill_ledger (unchanged)
  │  activate(budget)     PRIMARY skill = full body; others = compact cards
  ▼
System messages           total ≤ 7,000 chars — honors the 16k runtime ceiling
```

**Runtime discovery (the novel-task path):** two always-on core tools —

- `find_skill(query)` — bilingual ranked search over the local skill registry
  (name, description, capabilities, triggers). Returns metadata, never bodies.
- `use_skill(name)` — loads one skill's full playbook on demand (budget-capped).

So for work the router did not anticipate, the *agent* pulls the skill instead
of hoping the pre-injection pushed the right one. If nothing local matches,
`find_skill` says so explicitly and points to the external discovery pipeline
(`agent-find-skill` / `npx skills find`).

## Components

| Piece | File | Role |
|-------|------|------|
| Resolution engine | `backend/capability_skill_registry.py` | taxonomy, resolve, bind, activate, find, body |
| Runtime tools | `backend/builtin_tools.py` + `main.py exec_tool` | `find_skill`, `use_skill` (in `_TOOL_CORE`) |
| Injection | `main.py` (both call sites) | `activate_for_task()` with legacy-router fallback |
| Endpoints | `skill_router_endpoints.py` | `/api/skills/architecture`, `/resolve`, `/find` |
| UI | `index.html` Skills page | architecture tree + live resolve preview + find box |
| Metadata | `backend/skills/*/SKILL.md` | `capabilities:` field; Thai triggers; noise stripped |

## Rules

1. **Budget is law.** Total injected skill chars ≤ `ACTIVATION_BUDGET` (7,000).
   Primary skill body capped at 5,000; each extra skill is a ~400-char card
   ending with `use_skill("<name>")` so the model can pull the rest itself.
2. **Thai is substring-matched** (no word boundaries in Thai); English is
   token-matched. A capability needs score ≥ 2.0 to activate (one strong
   keyword or two weak ones) — this keeps the g4 no-false-positive golden.
3. **Legacy fallback.** If no capability resolves, the old trigger router runs
   at a *conservative* threshold (min_score 3.0). Delete it only after CSA
   covers its hit-rate (strangler-fig).
4. **Trust still applies.** skill_ledger trust factors weight skill ranking
   inside a capability, exactly as they weighted trigger scores before.

## Migration status

- [x] v1: engine + tools + endpoints + UI + metadata cleanup (this change)
- [ ] v2: capability resolution feeds `_select_tools_for_task` (one taxonomy
      for both skills and tools)
- [ ] v3: retire `skills_auto_router.match` from the injection path entirely
