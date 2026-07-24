# Agent Find Skill v2.0 - The Scout

A discovery specialist skill installed into SkynetClaw. Lives at
`backend/skills/agent-find-skill/`.

## Triggers

This skill auto-activates when the user message contains any of:

- find a tool / find tool
- look for a library / find library
- which library / which framework
- best library for / best framework / best tool for
- find a model / find a dataset
- search for an mcp
- vector database
- OCR
- หาเครื่องมือ (Thai: "find a tool")

The trigger match is performed by `skills_auto_router.match()` against the
incoming user text on every `/api/chat` and `/api/agent/run` call. No
manual UI activation needed.

## How it integrates with SkynetClaw

| Concern | Where |
|---|---|
| Skill body | `SKILL.md` in this folder |
| Discovery on boot | `hooks/20_skills_sync.py` walks `backend/skills/` |
| DB row | `skynerclaw.db` table `skills` |
| Trigger index | `skills_index.json` (rebuilt by `hooks/21_skills_index.py`) |
| Auto-injection | `main.py` calls `auto_skill_messages()` on every request |
| Genome write target | `backend/atlas_genome.json -> strategy_rules.discoveries[]` |

## 6-Phase Pipeline

1. **Need analysis** - restate, lock hard constraints, list soft prefs
2. **Genome check** - reuse prior recommendations if recent & still valid
3. **Multi-channel discovery** - registries + research + community signal
4. **Risk-adjusted eval** - Fit + Maturity - Risk - Cost
5. **Composition synthesis** - one primary + one fallback, integration hints
6. **Knowledge transfer** - emit YAML Genome entry, append to atlas_genome.json
