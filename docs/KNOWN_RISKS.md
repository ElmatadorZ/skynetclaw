# Known Risks

> Limitations are never hidden. Each risk is classified: **Implemented** (shipped +
> evidence) · **Pending** (shipped, evidence incomplete) · **N/A** (not implemented) ·
> **Blocked** (external/environmental) · **Future Work** (deferred, Post-RC backlog).
> Under [EPIC: Trust](EPIC_TRUST.md). Last updated: 2026-07-01.

## Implemented (shipped + evidence)
| Item | Evidence |
|---|---|
| Web-layer security C1–C3 (RCE off, key masking, path confinement, origin guard, localhost bind) | `security_regression_test.py` 10/10 |
| SQLite WAL at startup + hardened connect | chaos EXP-3/5/6 |
| Atomic settings save + corruption recovery + no `.tmp` leak | chaos EXP-1/2/7/8 (bug CHAOS-001 fixed) |
| ACID crash-safety (killed writer rolls back) | chaos EXP-4 |
| Perf: health/models/graph cached (2.3s→~11ms) | P1 latency probe |
| A11y layer (focus, ARIA, modal trap, live region, friendly errors) | browser eval, 0 console errors |
| WCAG 2.1 AA (contrast/names/lang/landmarks/target) | audit: 0 contrast fails/300 elts; `a11y_regression_test.py` 22/22 |
| Visual/decision-debt reduction (UI-0006/07/08/09/10/12) | measured contrast/sizes/Hick/decision-load |

## Pending (implemented, evidence incomplete — NOT PASS)
| Item | Missing evidence |
|---|---|
| Automated a11y in CI | WCAG 2.1 AA **measured + fixed** (0 contrast fails/300, 22/22 static regression, [ACCESSIBILITY_AUDIT](ACCESSIBILITY_AUDIT.md)); missing = **axe-core/Playwright in CI** + human-judgment criteria via RUV |
| Repeated-restart resilience | one live restart proven; **automated multi-restart / rapid kill loop** not yet a test |
| Two-process DB contention | single-process concurrency tested; **two processes on one DB** not tested |
| Real disk-full / permission-denied | simulated via monkeypatch (EXP-8); **real filesystem-full** not exercised |
| Agent-run latency SLA | model-bound; **no performance budget defined** for `/api/agent/run` |
| Lint standard | syntax-parse clean; **no configured linter** (ruff/flake8/eslint) |

## N/A (design-only — never counted as reliability)
| Item | Note |
|---|---|
| V3 kernels: Journal, Reality Boundary, Scheduler, Identity/Capability, Constitution, Epistemic, Supervisor, Contract Registry, Model Gateway | `docs/v3/*` designs only; **not implemented** |
| Mission resume after interruption | requires the (unshipped) Journal |
| Unit-test layer | no unit-test framework in repo |

## Blocked (external / environmental)
| Item | Detail |
|---|---|
| GPU execution via Ollama | Ollama's `cuda_v13` runner omits sm_86 → RTX 3060 falls back to CPU. Workaround: llama.cpp GPU server (ElmatadorZ). Upstream fix unreleased. See memory `ollama-gpu-sm86-cpu-fallback`. |

## Residual security risks (accepted, mitigated — documented, not closed)
| Risk | Mitigation | Residual |
|---|---|---|
| `/api/files/read|write` allow arbitrary local paths | localhost bind + origin guard; used by the file browser | a local drive-by from a sandboxed `null` origin could still reach them; **not fully sandboxed** |
| `SKYNET_ENABLE_EXEC=1` re-enables `/api/shell` & `/api/code/run` (RCE) | disabled by default; opt-in only | if an operator enables it, the RCE surface returns |
| API keys stored plaintext in SQLite | masked in API responses (C2) | at-rest encryption not implemented |

## Future Work (Post-RC backlog — do NOT implement during freeze)
UI-0013 hardcoded host · UI-0014 command palette · UI-0015 input labels · UI-0016 red ·
UI-0017 empty-state wording · at-rest key encryption · automated axe-core/Playwright a11y
in CI · automated multi-restart chaos · linter config. All tracked; none worked on until
the freeze lifts.

## Rule
An item moves **Pending → Implemented** only when a reproducible test/measurement is
added. An item is **never** marked PASS on this project without that evidence.
