# Belief Causal Theories — does belief cause behaviour, or only describe it?

> Recovering the competing positions on whether belief has *causal power* or is a *useful
> description*. Continues BELIEF_TAXONOMY / BELIEF_CRITERIA / BELIEF_OBSERVABILITY. Science
> first (philosophy of mind + causal inference). Tags: SUPPORTED (canonical position) / LIKELY
> / SPECULATIVE / UNKNOWN / FALSIFIED. No software, no Genesis.

## The organizing problem (SUPPORTED) — the Exclusion Argument (Kim)
The whole debate is forced by one argument (Jaegwon Kim): if **(a)** every physical effect has
a sufficient physical cause (causal closure), **(b)** the mental is not identical to the
physical (non-reductivism), and **(c)** effects aren't systematically overdetermined, then the
mental (belief) is **excluded** from causing behaviour — the physical realizer does all the
work. Every position below is a response to this argument. Whether belief causes anything turns
on how one escapes exclusion.

## The positions

### P1 · Causal realism / physicalist functionalism · SUPPORTED (Fodor; Dretske)
Beliefs are functional states realized physically; they **cause** behaviour and figure in
*ceteris paribus* psychological laws. Escapes exclusion by **identity/realization** (the belief
just *is* the state that causes) or by higher-level difference-making. Content is causally
relevant (Dretske: content as a **structuring cause** — it explains *why the behaviour is of
that type*, distinct from the physical **triggering cause**).

### P2 · Dispositionalism · SUPPORTED (Ryle)
A belief is a *disposition*, not a hidden occurrent cause. "Fragile" doesn't name a secret
inner cause; it summarizes a counterfactual pattern whose *categorical base* does the pushing.
Belief is **causally relevant** (the pattern is real) without being an **efficient cause** in
its own right. Sidesteps exclusion by not positing an extra causer.

### P3 · Belief as latent variable · SUPPORTED (psychometrics; cognitive modelling)
Belief is an **inferred hidden variable** in a model (like a latent node in a Bayes net, or
"g"). It is real *to the degree it earns its place* in the model. **Causal iff** the latent is
given interventional import (do(belief) predicts); **instrumental iff** it only improves fit.
Status is *model-relative*.

### P4 · Real Patterns · SUPPORTED (Dennett, "Real Patterns")
Belief-talk tracks **real patterns** — mind-independent compressions of behavioural
regularity (real because the compression genuinely holds, not any-pattern-goes). The pattern is
**predictively indispensable** yet the *pushing and pulling* happens at the physical level. A
middle position: belief is real and predictively load-bearing but not a *separate* efficient
cause.

### P5 · Instrumentalism / explanatory fiction · SUPPORTED (Dennett intentional-stance reading; van Fraassen-style anti-realism)
Belief-talk is a **stance/tool**: adopt it because it predicts, not because it names an entity.
Theoretical terms need not refer to be useful (constructive empiricism). Belief has
**predictive** warrant, **no committed causal** claim.

### P6 · Eliminativism · SUPPORTED (Churchland)
Folk psychology is a **false, stagnant theory**; "belief" refers to nothing; a mature
neuroscience will replace it. Belief **causes nothing because there are no beliefs**. The
strongest denial of causal status.

### P7 · Computational / representational state · SUPPORTED (Fodor RTM; Stich)
Belief is a **computational state** over representations; the **computation** causes behaviour.
Content either does causal work via its syntactic vehicle (Stich: syntax causes, semantics
rides along — a *content-epiphenomenalist* leaning) or via representation (Fodor: the
representation, bearing content, causes).

### P8 · Anomalous monism · SUPPORTED (Davidson)
Mental events are **token-identical** to physical events, hence causally efficacious *as*
physical events — but there are **no strict psychophysical laws**, so the mental *qua mental*
(under its belief-description) does not figure in causal laws. Leaves the notorious worry: does
belief do work *as belief* or only *as its physical token*? (Kim presses exactly here.)

### P9 · Epiphenomenalism (about content / the mental) · SUPPORTED as a position (cf. Jackson on qualia)
The mental (or specifically **content**) is **caused by** the physical but **causes nothing**.
Belief-content is a causal dead end; only the vehicle matters. The limiting denial short of
eliminativism (beliefs exist but are inert).

## The interventionist reframing (SUPPORTED) — Woodward; Pearl
Modern causal inference **operationalizes** the dispute: **X causes Y iff an intervention on X
changes Y** (Woodward). This dissolves much of the metaphysics: if manipulating belief (holding
confounds fixed) reliably changes behaviour, belief is a cause **by this criterion** — and
higher-level variables can be *better* (more **proportional / stable**) difference-makers than
their physical realizers (Yablo; List & Menzies). Interventionism is the bridge from the
philosophical positions (P1–P9) to testable predictions (BELIEF_CAUSAL_TESTS).

## The landscape, mapped
| Position | Belief causes? | Belief predicts? | Escapes Kim by |
|---|---|---|---|
| P1 realism/functionalism | **Yes** | Yes | identity/realization; difference-making |
| P2 dispositionalism | causally *relevant*, not efficient | Yes | no extra causer |
| P3 latent variable | *iff* interventional | Yes | model-relative |
| P4 real patterns | at physical level; pattern real | **Yes (indispensable)** | pattern-realism |
| P5 instrumentalism | no claim | Yes | doesn't try (tool) |
| P6 eliminativism | **No (no beliefs)** | superseded | denies the relata |
| P7 computational | yes (computation); content contested | Yes | computation = cause |
| P8 anomalous monism | as physical token; *qua mental* contested | Yes | token identity |
| P9 epiphenomenalism | **No (inert)** | Yes | accepts exclusion |

**The live scientific question is not "cause or not?" in the abstract, but "does belief make an
interventional difference at its own grain?"** — recovered next.
