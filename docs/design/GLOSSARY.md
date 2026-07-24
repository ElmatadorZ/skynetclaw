# SkynetClaw Glossary (UI-0012)

> Plain-language definitions of the in-house vocabulary. Goal: a first-time user should
> never have to *guess* what a domain word means (Nielsen #2 — match the real world).
> Key terms also surface as `title` tooltips in the UI (Council, Intel done; more to
> follow). Keep this list short and jargon-free.

| Term | In one line | Where you see it |
|---|---|---|
| **House** / THE HOUSE | The whole running system — its agents, memory, and missions, as one organism. | branding, mission ledger |
| **ElmatadorZ** | The local model that powers execution (Qwen2.5-14B served by llama.cpp). | model name, header |
| **Mission** | One job the system is asked to complete, from request to result. | agent runs, ledger |
| **Council** / Continental Division | A group of specialist agents that discuss and vote before deciding — not a single AI. | Council tab |
| **Governor** | The agent that presides over the Council and enforces the rules. | Council |
| **Commander** | The top authority that sets intent and can override. | Council |
| **Concierge** | The agent that receives a request and routes it (intake/triage). | Council |
| **Atlas** | The global-intelligence/strategy agent. | Council |
| **Agent** | One AI worker with a role (Analyst, Scout, Skeptic, …). | everywhere |
| **Skill** | A reusable capability the agent can switch on for a task (e.g. dashboard builder). | Skills tab |
| **Tool** | A concrete action the agent can call (search, write file, read document, …). | Tools tab |
| **Runtime / Connection** | A model backend the app talks to (local llama.cpp/Ollama or a cloud provider). | Connections tab |
| **Intel** | The system dashboard — a live map of agents, tools, skills, and runtimes. | Intel tab |
| **Reflection** | What the system learns after a mission (what worked, what to remember). | (engine) |
| **Governance / GPS-2** | The safety gate every action passes (deny-by-default, human approval for risky actions). | (engine) |

## Rule
When a screen first shows one of these words, give it a `title` tooltip pointing back to
this definition. Don't make the user hold the whole vocabulary in their head
(Nielsen #6 — recognition over recall).
