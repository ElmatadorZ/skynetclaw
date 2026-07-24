# 03 — Decay & Transfer

> Pure epistemology. Deliverables 5 (Decay) & 6 (Transfer) + Questions 5 (does
> warrant decay, when) & 6 (does warrant transfer, where is it lost). Recovered,
> falsifiable, tagged.

---

## Q5 / D5 · Decay — does warrant weaken, and when?

**Recovered thesis: warrant decays, but the decay law is set by the warrant's KIND
(the a priori / a posteriori cut from file 00). Decay is defeat over time.**

**Mechanisms of decay (recovered):**
- **D-defeat** — a *defeater* arrives (rebutting or undercutting, file 02). This is
  the primary, discrete decay: warrant drops when an undefeated defeater appears.
  SUPPORTED (Pollock).
- **D-staleness** — the ground is *time-indexed* and the world moves. Empirical
  warrant for "it is raining" decays with elapsed time even absent any new evidence,
  because observation warrants a *time-stamped* proposition; re-timing it is
  inference, at lower warrant. SUPPORTED (this is the epistemic content of
  "freshness").
- **D-source-drift** — testimonial/predictive warrant decays as the *source's*
  reliability changes (a once-reliable instrument drifts; a model's calibration
  rots). SUPPORTED.
- **D-transmission** — warrant lost in a chain (Q6).

**The decay asymmetry (central, SUPPORTED):**
- **A priori warrant (logical, mathematical) does not decay by staleness.** A proof
  is not weakened by the passage of time or new empirical data. It can be lost only
  by *discovery of error* in the proof itself — a discrete D-defeat, not gradual
  decay. "2+2=4" is exactly as warranted next century.
- **A posteriori warrant decays continuously** (staleness + defeat + drift). Its
  half-life is set by how fast its domain changes and how defeasible its ground is.

**A recoverable near-law (LIKELY):** warrant-at-time-t ≈ warrant-at-acquisition
minus accumulated defeat, where staleness contributes a domain-specific decay term
that is **zero for the a priori** and positive for the a posteriori. This is not a
quantitative theorem (no units on warrant, file 05) but an ordinal one: *older
empirical warrant is weaker, ceteris paribus; older proof is not.*

**Falsifier:** an a-posteriori warrant that provably never stales (would refute
D-staleness's universality over the empirical), or an a-priori warrant that decays
with time absent discovered error (would refute the asymmetry).

## Q6 / D6 · Transfer — does warrant move, and where is it lost?

Warrant *transfers* along chains: `experiment → paper → citation → textbook →
teacher → student → answer`. The mission's chain `paper → citation → model → agent
→ answer` is the same structure. This is **testimonial warrant** (file 00: a
transfer, not a source). Recovered results:

**T1 · Transfer is real but not conservative.** Warrant is not conserved across a
link the way energy is; each link can only *lose*, never *manufacture*, warrant. A
conclusion cannot end more warranted than its chain permits. SUPPORTED.

**T2 · The transmission bound (the key result).** Warrant received ≤
```
  min( source_warrant,           ← you can't transmit more than you had
       channel_fidelity,          ← corruption, mistranslation, context-stripping
       receiver_assessment_capacity )   ← you can't absorb what you can't evaluate
```
The chain is **weakest-link (min), further attenuated by fidelity**. LIKELY — this
synthesizes the testimony literature (Coady; Fricker) into an information-flavored
bound; it is offered as the best recovered structure, refutable by a case of
faithful high-absorption transfer that still loses warrant for none of these three
reasons.

**T3 · Where warrant leaks (the four loss points, recovered):**
1. **Source misrepresentation** — the origin never had the claimed warrant
   (fabricated data upstream); the whole chain inherits a phantom.
2. **Context-stripping** — a claim warranted *in context C* (assumptions, scope,
   error bars) is transmitted *without C*; the receiver over-extends it. The most
   silent leak: nothing looks corrupted, yet the warrant is gone because its
   conditions travelled separately or not at all. SUPPORTED.
3. **Transmission corruption** — mistranslation, summary distortion, citation of a
   citation of a citation (the "citation cascade" where the original said less than
   the chain claims). SUPPORTED (documented in citation-error studies).
4. **Receiver incapacity** — the receiver cannot assess the source, so cannot
   distinguish warranted from unwarranted testimony; they absorb both at face value.
   Warrant that the receiver cannot evaluate is, for them, not warrant but faith.

**T4 · The reductionism/anti-reductionism axis (CONTESTED).** *Does the receiver
need independent reason to trust the source (Hume/reductionism), or is testimony
prima-facie warranted by default (Reid/anti-reductionism)?* This is unresolved and
it sets whether "receiver_assessment_capacity" is a hard gate (Hume) or a defeater-
only condition (Reid). CONTESTED — the live fault line in transfer.

**Recovered corollary (the citation-cascade theorem, LIKELY):** in a chain where
each link strips a little context and cannot fully assess its predecessor, warrant
decays *geometrically* with chain length even if every link is honest. Distance from
the origin is itself a defeater. This is why "primary source" carries epistemic
weight the tenth-hand report does not — not distrust of intermediaries, but the
compounding of T2's min-with-fidelity over length.

**Falsifier:** a long transfer chain that demonstrably preserves full warrant to the
terminus without any link independently reconstructing the original ground — would
refute T2/the cascade corollary.
