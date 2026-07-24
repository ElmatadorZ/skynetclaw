# Belief Causal Tests — experiments that could falsify each theory

> For each position (BELIEF_CAUSAL_THEORIES), the observable prediction that changes if it is
> true, and the experiment that could falsify it. Built on the interventionist criterion
> (Woodward: cause = invariance under intervention) and causal-inference tooling (Pearl
> do-calculus, mediation, ablation/lesion). Tags: SUPPORTED / LIKELY / SPECULATIVE / UNKNOWN.

## The shared instrument (SUPPORTED)
All tests reduce to variants of: **manipulate the putative belief; hold confounds fixed;
measure whether behaviour changes in the predicted, invariant way.**
- **Intervention (Woodward):** do(belief) via induced/removed belief (persuasion, false
  feedback, evidence) — controlled against a placebo that changes everything *except* the belief.
- **Mediation (Pearl; Imai):** does belief lie on the path stimulus→behaviour? Test whether
  conditioning on belief **screens off** stimulus from response.
- **Ablation / lesion (neuroscience):** disrupt the substrate realizing the belief; look for a
  **specific** behavioural deficit (double dissociation).

## Per-theory falsifiers
| Theory | Prediction if true | Falsified if… |
|---|---|---|
| **P1 realism/functionalism** | do(belief) changes behaviour invariantly across backgrounds; belief mediates stimulus→response | intervening on belief (confounds controlled) **never** changes behaviour, OR belief never screens off stimulus |
| **P2 dispositionalism** | the counterfactual *pattern* holds; no *extra* occurrent intervening cause is needed to predict it | a hidden occurrent state is found that does causal work the dispositional description **cannot** capture (mechanism outruns the disposition) |
| **P3 latent variable** | adding the belief-latent **improves** predictive fit and its do() has import | dropping the latent leaves fit **unchanged** (superfluous), OR the latent has no interventional consequence → demote to instrumental |
| **P4 real patterns** | belief-talk yields **compression/prediction** no lower-level description matches at that grain | belief-talk adds **zero** compression/prediction over the physical description → not even a real pattern |
| **P5 instrumentalism** | belief-talk is **predictively useful**; makes no distinctive interventional claim | belief-talk is predictively **useless** (fails to beat a null model) → the tool is idle |
| **P6 eliminativism** | lower-level (neural) description **captures and surpasses** all belief-level regularities | a robust, **projectible, multiply-realized** belief-level generalization exists that **no** lower-level description recovers (Fodor's special-sciences argument) |
| **P7 computational** | behaviour tracks the **computational state**; disrupt the computation → predicted behaviour change | behaviour **dissociates** from the computational state (right computation, wrong behaviour, or vice versa) |
| **P8 anomalous monism** | mental events cause *as physical tokens*; no strict psych laws | a **strict** psychophysical law is found (falsifies the anomalism), OR the mental token has no efficacy under any description |
| **P9 epiphenomenalism** | intervening on the **mental/content** changes **nothing**; only the vehicle matters | intervening on belief **does** change behaviour with the content as the difference-maker (see BELIEF_CAUSAL_SIGNATURES) → inertness falsified |

## The decisive real-world evidence (SUPPORTED)
- **Belief-manipulation studies** (persuasion, false-feedback, framing) reliably change
  downstream behaviour with confounds controlled → satisfies the **interventionist** criterion
  → **P9 epiphenomenalism about the belief-STATE is FALSIFIED** (empirically, manipulating
  belief changes outcomes). This is the strongest single result in the whole area.
- **Lesion/disruption** of belief-supporting substrates yields **specific** behavioural deficits
  (e.g., false-belief reasoning deficits with specific temporo-parietal disruption) → the
  belief-realizing substrate is causally implicated.

## What the tests can and cannot settle (SUPPORTED)
- **Can settle (empirically):** that the **belief-state** is an interventional difference-maker
  (P1/P3-causal/P7 supported; P9-about-state falsified).
- **Cannot cleanly settle:** whether the **content** (belief's aboutness) or only the **vehicle**
  is efficacious (P7-Stich vs Dretske) — this needs interventions that vary *content while
  holding the vehicle fixed*, which are **hard/UNKNOWN** to realize (content and vehicle
  co-vary). → **content-causation remains LIKELY (via Dretske structuring-cause), not
  SUPPORTED-clean.**
- **Cannot settle by experiment:** the pure metaphysics of exclusion (P8/anomalous monism) —
  it is compatible with the same evidence (UNKNOWN, a matter of interpretation).
