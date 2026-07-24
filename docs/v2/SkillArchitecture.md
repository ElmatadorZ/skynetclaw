# Skill Architecture & Dependency Graph

> Skills as first-class, auto-discovered plugins, organized by an explicit dependency
> graph: skills→skills, agents→skills, tools→services, services→runtimes.
> Parent: [Architecture](Architecture.md) · Built on `skills_auto_router.py` +
> `skills/*/SKILL.md`, `BUILTIN_TOOLS`/`TOOL_CATEGORY`, the OS service layer.

## 1. Skill as a plugin
A skill is a folder with a `SKILL.md` (metadata + guidance) discovered by
`skills_auto_router.py` — no registration in code. This already works
(`web-dashboard-builder`, `obsidian-knowledge-protocol`, `agent-find-skill`). V2
keeps the format and adds an explicit dependency declaration.

```yaml
# SKILL.md frontmatter (V2 additions marked *)
name: web-dashboard-builder
role: build self-contained HTML dashboards/reports
trigger_phrases: [dashboard, html, report, chart, สรุปข่าว, infographic]
requires_tools:    [build_news_report, write_file, get_news]   # *
requires_services: [filesystem, network]                        # *
requires_skills:   []                                           # *
provides:          [html-artifact]                              # *
budget_chars: 24000                                             # * (context cap)
```
The router selects skills by trigger match (existing) and now also resolves their
`requires_*` closure so the needed tools/services are guaranteed available.

## 2. The Dependency Graph
A single typed graph over the system (the *system subgraph* of the
[Knowledge Graph](KnowledgeGraph.md), already emitted by `system_graph.py`):
```
Skill   --needs-->  Skill
Agent   --uses-->   Skill
Skill   --needs-->  ToolCategory
Tool    --needs-->  Service          (e.g. get_news → network)
Service --needs-->  Runtime          (e.g. execution → ElmatadorZ runtime)
```
`system_graph.build_graph()` already produces runtime/agent/skill/tool/service nodes
and `uses`/`needs`/`executes-on`/`serves` edges — V2 enriches edges from the
`requires_*` declarations instead of the current hand-coded `_skill_links` map.

## 3. Resolution & validation
- **Resolve**: before a skill runs, compute the transitive closure of its
  dependencies; if a required service/runtime is offline, the skill is unavailable
  (mission node BLOCKED with a precise reason) rather than failing mid-run.
- **Validate at boot**: `runtime_boot.py` checks the dependency graph for missing
  edges (skill needs a tool that doesn't exist) and reports them — fail-fast.
- **Cycle detection**: skill→skill edges are checked for cycles at load.

## 4. Interfaces (DI / plugin)
```python
class Skill(Protocol):
    name: str; trigger_phrases: list[str]
    requires_tools: list[str]; requires_services: list[str]; requires_skills: list[str]
    def guidance(self) -> str          # SKILL.md body, budget-capped
    def applies(self, task: str) -> float

class SkillRegistry:                    # wraps skills_auto_router
    def discover(self) -> list[Skill]
    def select(self, task, *, budget) -> list[Skill]
    def resolve(self, skill) -> Closure  # tools+services+runtimes needed

class DependencyGraph:
    def of(self, node_id) -> Subgraph
    def validate(self) -> list[Issue]
    def visualize(self) -> GraphJSON     # → dashboard node map
```

## 5. Tools & services
- Tools stay in `BUILTIN_TOOLS` with categories in `TOOL_CATEGORY`
  (`get_tool_cat`). A tool declares its backing service (network/filesystem/…); the
  service declares its runtime where relevant.
- Services are the existing OS services (`genesis_os.services`); they expose `state`
  so the dependency graph knows what's runnable.

## 6. Compatibility
- Existing `SKILL.md` files work unchanged; `requires_*` are optional and default to
  empty (skill assumed self-sufficient) — additive, no breakage.
- The budget cap (24000 chars) already enforced in the frontend chat builder is moved
  into the registry so it applies uniformly.
- The dependency graph reuses `system_graph.py`; the dashboard node map (now
  secondary) renders it.
