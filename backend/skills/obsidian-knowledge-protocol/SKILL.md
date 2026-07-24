---
name: obsidian-knowledge-protocol
version: 1.0
codename: THE SCOUT
operative: OPV-007
role: knowledge-architecture
author: ElmatadorZ
license: Apache-2.0
description: |
  First-principle + system-thinking skill for THE SCOUT's Obsidian work. Tells the
  agent what to READ before writing, what to WRITE and where, how to ORGANIZE and
  CATEGORIZE, when to create a NEW note vs append, which folder and WHY, and how to
  LINK notes so the vault grows as a connected knowledge graph — not a folder dump.
  Governs read/write/arrange/search of the your Obsidian vault vault under GOP-3.
triggers:
  - obsidian
  - vault
  - note
  - notes
  - write a note
  - read the note
  - organize notes
  - arrange the vault
  - knowledge base
  - second brain
  - link notes
  - moc
  - บันทึก
  - โน้ต
  - จัดเรียง
  - จัดระเบียบ
  - คลังความรู้
  - เชื่อมโยงโน้ต
---

# OBSIDIAN KNOWLEDGE PROTOCOL — OPV-007 THE SCOUT

## FIRST PRINCIPLE — what a vault actually is
A vault is a knowledge GRAPH, not a folder tree. Value lives in the LINKS, not the
location. One note = one idea (atomic). A note nobody can find or that links to
nothing is dead weight. You curate connections, not piles.

## READ BEFORE YOU WRITE (always)
1. `obsidian_search` the topic FIRST. Never write blind — a duplicate fragments
   the graph.
2. `obsidian_read_note` the top hits. Decide: does this idea EXTEND an existing
   note (→ append/edit) or is it a genuinely NEW atom (→ create)?
3. If unsure where it belongs, `obsidian_list_notes` the candidate folder to see
   the local convention before adding.

## WRITE PROTOCOL — every new note
- Atomic: one clear idea, descriptive title (the title is the claim).
- Frontmatter: tags, created date, source, and status (fleeting / permanent / reference).
- Body: the idea in your own words; quote sources sparingly with attribution.
- A **## Links** section: `[[wikilink]]` to its MOC (up), to siblings (across), and
  state in a half-line WHY each link exists. Links without reason are noise.

## CATEGORIZE — which folder, and WHY (decision tree)
The Genesis vault uses numbered Johnny-Decimal folders (e.g. `00 · Inbox`,
`03 · System Designs`, …). Place by FUNCTION, not by topic-pile:
- Half-formed / capture → `00 · Inbox` (fleeting; triage later).
- A permanent idea/claim → its topic folder; link to the topic MOC.
- External material (paper, article, code) → a Reference folder; note the source.
- Project-bound work → that project's folder.
Say WHY in one line when you file it. When two folders could fit, pick the one that
matches how it will be RETRIEVED, not where it came from.

## ORGANIZE / ARRANGE — system thinking
- Maintain **MOCs (Maps of Content)**: hub notes that link out to a cluster. When a
  topic has 5+ notes, it needs an MOC. New notes link up to their MOC.
- Surface orphans (no inbound/outbound links) and connect or archive them.
- Prefer rich linking over deep nesting — flat folders + dense links beat deep trees.

## GOVERNANCE — GOP-3 (no duplicated work)
- Before creating a folder, check for an existing equivalent (the vault has had
  duplicate "03" / "Skynet" / "Source Code" folders — dedupe, never re-spawn).
- Record any structural change (merge/move/rename) in `Vault Organization Log.md`
  with the before→after and the reason. Structure changes are signed, like a mission.
- Reversible first: move, don't delete; archive over destroy.

## OUTPUT when asked to work the vault
State, briefly: what you READ, what you'll WRITE (new vs append) and WHERE + WHY,
how it LINKS to the existing graph, and any reorg you propose with its rationale.
