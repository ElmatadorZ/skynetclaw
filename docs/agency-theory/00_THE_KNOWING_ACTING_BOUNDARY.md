# 00 — The Knowing–Acting Boundary (the hinge of the stack)

> Pure philosophy. Recover, do not invent. Everything falsifiable. This is the
> hinge document: it records the correction that the epistemology stack is complete
> only as a **Theory of Knowing**, makes the boundary to the **Theory of Agency**
> rigorous, and opens Part II as a distinct domain — not a tail of Part I. It is an
> entry-spec, not the Part II theory itself. Tags: SUPPORTED / LIKELY / CONTESTED /
> OPEN.

---

## The correction (accepted, and made precise)

The prior claim "the stack is closed" was an **overclaim** — by the stack's own C1
it should not have been asserted at that grade. What is closed is the **Theory of
Knowing**: belief → observation → causation → boundaries → estimation → evaluation →
meta-evaluation → warrant → inquiry. Every one of those answers a **truth-apt**
question — its answers are true or false, and *warrant* is the licence to hold them.

Agency asks a categorically different kind of question, and the difference is not of
degree but of **kind**. Three recovered ways to name the same cut:

- **Hume's guillotine (SUPPORTED).** No "ought" follows from an "is" alone. The
  Theory of Knowing is entirely "is". Therefore Part II *cannot be derived from Part
  I* — it requires its own primitives (goals, values, preferences). This is the
  formal reason Agency is a new domain, not an extension.
- **Theoretical vs practical reason (Kant, SUPPORTED).** Theoretical reason aims at
  *what is true*; practical reason at *what to do*. Different faculties, different
  norms.
- **Direction of fit — the sharpest, and already ours (SUPPORTED).** The belief-
  science recovery isolated exactly this axis: *belief* has **mind-to-world** fit
  (adjust the mind until it matches the world — truth). *Intention/desire* has
  **world-to-mind** fit (adjust the world until it matches the goal — success). **Part
  I is the entire mind-to-world half; Part II is the world-to-mind half.** The stack
  did not "end"; it reached the axis and stopped at the belief pole. Agency is the
  same axis, run the other direction.

## What changes when you cross the boundary (the normativity swap)

| | Theory of Knowing (Part I) | Theory of Agency (Part II) |
|---|---|---|
| Question | what is true? | what should be done? |
| Direction of fit | mind → world | world → mind |
| Success | truth / accuracy | goal-attainment / value |
| Its "licence" | **warrant** (licence to believe) | **justification** (licence to act) |
| Failure of overreach | overclaim (assert beyond warrant) | recklessness (act beyond justification) |
| Failure of underreach | blindness (deny known) | paralysis (fail to act on sufficient justification) |
| Primitive it needs | evidence | **value / goal** (not derivable from evidence — Hume) |
| Time | mostly retrospective (what is/was) | intrinsically prospective (what will result) |

**The load-bearing consequence:** warrant is to belief as **justification is to
action** — a different currency, not more of the same. A perfectly warranted belief
does not tell you what to do; that needs a value the world of facts cannot supply.
SUPPORTED (Hume). So Part II has its own C1-analog: *the licence to act is bounded
above not by warrant but by justification, which is warrant-about-consequences
combined with a value* — a compound the Knowing stack cannot produce alone.

## The deep symmetry (Part II is Part I mirrored under fit-reversal)

Because Agency is the same axis reversed, each Part-I theory has a Part-II shadow.
This is recovered structure, not decoration — it predicts what theories Part II needs:

| Part I (Knowing) | Part II (Agency) shadow | Shared axis |
|---|---|---|
| **Belief** (mind-to-world disposition) | **Policy** (world-to-mind disposition) — a counterfactually-invariant disposition *to act* | both are dispositions (belief-science's invariance, run both ways) |
| **Warrant** (licence to believe) | **Justification** (licence to act) | normativity of licence |
| **Inquiry** (what to ask to reduce Unknown) | **Planning** (what to do to reduce the goal-gap) | both minimize a gap per cost |
| **Estimation** (belief under uncertainty) | **Decision** (action under uncertainty) | the *same* probability/cost machinery **transfers** |
| **Evidence / Observation** | **Outcome / Observation** | Observation is **shared** — the one node in both loops |
| **Causation** (does belief cause?) | **Intervention** (does acting change the world?) — Pearl's do-calculus | the interventionist causation recovered in belief-science *is already the Part-II tool* |
| **Evaluation / CEE** | **Governance** (evaluate/constrain action) | normativity applied to the object |

Two things this symmetry tells us immediately (LIKELY):
1. **What transfers across the boundary:** the uncertainty/estimation/cost machinery
   (decision-under-uncertainty *is* estimation with a value attached), and the
   interventionist causation (do-calculus was recovered on the Knowing side but is a
   *doing* concept — intervention). Part II does not rebuild these.
2. **What does NOT transfer:** the truth-aim (A2 of warrant) and the observed→unknown
   warrant lattice. They are replaced by a value-order and a consequence structure.
   Importing truth-normativity into action is a category error (the is/ought crossing).

## Where the bridge sits (why the CEE slice is the crossing point)

The two loops share exactly one node — **Observation** — and they meet there:

```
   KNOWING loop:  question → observe → evidence → belief → warrant → KNOWLEDGE
                                 ▲                                        │
                                 │                                        ▼
   ACTING loop:   ... ← OBSERVE outcome ← intervene ← act ← decide ← ────┘
```

Knowledge exits the Knowing loop and *enters* the Acting loop at **Decision**; the
Acting loop changes the world and returns at **Observe outcome**, which re-enters the
Knowing loop as evidence. The system is one figure-eight through the shared
Observation node.

**CEE (persist observation log + overclaim detector) is precisely the instrument at
that shared node.** It is where the theory first *touches the real world*: it observes
what actually happened (outcomes and internal events) and enforces C1 (no belief
beyond warrant) on the stream. That is why the correct first build slice is also the
*bridge*: it is neither purely Knowing nor purely Acting — it is the sensor both loops
share. Building it makes C1 a **runtime invariant** and simultaneously stands up the
one node Part II will require. SUPPORTED as the placement; the Acting-loop theory
above it is OPEN.

## Part II — the open domain (its nodes and their governing questions)

Stated as an agenda, not answered here. Each is a distinct sub-theory with its own
primitives, and each names the discipline it must recover from:

| Node | Governing question | Recover from |
|---|---|---|
| **Decision** | what to choose under uncertainty + value? | decision theory (EU), bounded rationality (Simon), the frame problem |
| **Action** | what *is* an action; intention vs behaviour? | action theory (Anscombe, Davidson), basic vs derived acts |
| **Execution** | how does intention become effect; the trying/doing gap? | control theory, motor intention, deviant causal chains |
| **Intervention** | how does acting change the world causally? | Pearl do-calculus (already recovered) |
| **Outcome** | what actually resulted; intended vs actual? | the shared Observation node; error/regret |
| **Learning** | how does outcome update the disposition to act? | RL, credit assignment, the exploration/exploitation trade |
| **Policy** | what is a standing, counterfactually-invariant disposition to act? | belief-science's invariance, world-to-mind |
| **Governance** | which actions are permissible; the irreversible, authority, rights? | ethics of action, constraints, the veto |

**Falsifier for this whole hinge:** show that some Part-II node *is* derivable from
the Knowing stack alone (would refute the Hume-cut and collapse Part II into Part I),
or that Agency shares no structure with Cognition (would refute the fit-reversal
symmetry). Neither is expected; both are stated so the boundary is a claim, not a
decree.

## Status
Part I (Theory of Knowing): **complete as a system** (nine theories, evidence-first,
red-teamed). Part II (Theory of Agency): **open** — this document is only its door and
its map. The project is no longer "an epistemology"; it is a **Theory of Cognition +
a Theory of Agency joined at the Observation node**, of which only the first half is
built. Naming that honestly — not calling the half a whole — is the correction, and
it is itself an instance of C1.
