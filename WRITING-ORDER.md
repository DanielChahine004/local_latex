# Writing order

Ranked by **information flow**, not difficulty. A section is "ready" when the
things it must reference already exist; a section is "blocked" when writing it
early means guessing at a conclusion you have not reached yet.

Three constraints drive the whole ordering, and all three come from your own
`\topics` annotations:

- **§2.10 Summary and Research Gap is pure synthesis.** It re-reads §2.2–§2.9
  and introduces no new literature, so it cannot precede them. The old §2.9
  "Contemporary Directions" was cut for being a second, redundant pass at the
  same job (see Notes); each pipeline section now carries its own
  "where this is heading" material instead.
- **§2.7.8 is the gap the PhD targets.** To argue a gap exists you need the
  baseline it is missing from: §2.7.1, §2.7.4, §2.7.7 and §2.6.5.
- **Chapter 1's back half (§1.3–§1.6) is the payoff of the review**, not its
  preamble. §1.5 Candidate Research Directions is the thesis's actual argument.
  Writing it now commits you to a direction the review has not yet justified.

---

## Wave 1 — write now, blocked by nothing

Self-contained, textbook or historical. No section below depends on a
conclusion you have not formed. This is where to build momentum.

- [ ] §2.2.1 Origins: Positron Imaging Before Tomography
- [ ] §2.2.2 The First Tomographic Scanners
- [ ] §2.2.3 Key Milestones: Block Detectors, 3D, TOF
- [ ] §2.2.4 The Modern Era: Digital PET and Total-Body
- [ ] §2.3.1 Positron Emission, Annihilation and Coincidence Detection
- [ ] §2.3.2 Radionuclide Production: Cyclotrons and Generators
- [ ] §2.3.3 Common Radiotracers and Their Applications
- [ ] §2.3.4 Physical Limits on Spatial Resolution
- [ ] §2.3.5 Interaction of 511 keV Photons with Matter
- [ ] §2.4.1 Scintillation Mechanisms and Figures of Merit *(inorganic half
      already part-written; the organic mechanism still needs writing)*
- [ ] §2.4.2 Inorganic Crystals and Ceramics
- [ ] §2.5.1 Photomultiplier Tubes and the Anger Logic Legacy
- [ ] §2.5.2 Avalanche Photodiodes and Silicon Photomultipliers

§2.3.1 and §2.3.4 overlap §1.1, which is already written — reuse it, and
decide now which one owns the detail so you are not maintaining it twice.

Keep a scrappy note of what you have already searched. Not a discipline, just
insurance against redoing the same searches — the formal methodology section
this would have fed is gone (see Notes).

## Wave 2 — needs Wave 1's vocabulary, otherwise independent

- [ ] §2.4.3 Organic Scintillators: Plastics and Liquids *(needs 2.4.1's
      organic mechanism and 2.4.2 as the contrast — this is the extreme cost
      play, so it carries weight for the thesis)*
- [ ] §2.4.4 Composite and Nanostructured Scintillators *(needs 2.4.2 and 2.4.3
      — the category only makes sense as a hybrid of the two)*
- [ ] §2.4.5 Detector Segmentation: Pixellated vs Monolithic *(needs 2.4.2)*
- [ ] §2.4.6 Depth-of-Interaction Encoding *(needs 2.4.5)*
- [ ] §2.5.3 Readout ASICs and Channel Multiplexing
- [ ] §2.5.4 Digitisation, Triggering and Coincidence Processing
- [ ] §2.5.5 Timing Performance and TOF Readout *(needs 2.4.2, 2.5.2)*
- [ ] §2.6.1 The Conventional Cylindrical Scanner *(needs 2.4, 2.5 — this is
      the baseline every later architecture is defined against; do it first
      within §2.6)*
- [ ] §2.6.2 Preclinical and Small-Animal Systems
- [ ] §2.6.3 Organ-Specific Systems
- [ ] §2.6.4 Total-Body PET
- [ ] §2.7.1 Data Representations: Sinograms and List-Mode
- [ ] §2.7.2 Analytical Reconstruction: FBP
- [ ] §2.7.3 Iterative Reconstruction: MLEM, OSEM
- [ ] §2.7.4 System Matrix Modelling and Ray Tracing
- [ ] §2.7.5 Data Corrections
- [ ] §2.8.3 Monte Carlo Simulation as a Training Data Source
- [ ] §2.9.1 Clinical Applications
- [ ] §2.9.2 Sensitivity, Dose and Throughput Trade-offs

## Wave 3 — the argument-bearing sections

These are where your contribution gets positioned. Each needs a baseline from
Wave 2 to be *contrasted against* — that contrast is the point.

- [ ] §2.9.3 Scanner Cost Structure *(needs 2.4.2, 2.5.2 — **unblocks §1.2**,
      which currently cites nothing and stops mid-sentence)*
- [ ] §2.6.5 Unconventional Geometries *(needs 2.6.1 as the baseline, 2.4.5 for
      monolithic slabs)*
- [ ] §2.6.6 Case Studies of Research Scanner Programmes *(needs 2.6.1–2.6.5)*
- [ ] §2.7.6 TOF and DOI in Reconstruction *(needs 2.5.5, 2.4.6, 2.7.3)*
- [ ] §2.7.7 Open-Source Reconstruction Packages *(needs 2.7.4 — you are
      assessing their geometric assumptions, which needs the system matrix
      first)*
- [ ] §2.8.1 Neural Event Localisation *(needs 2.4.5)*
- [ ] §2.8.2 Learned Reconstruction and Denoising *(needs 2.7)*
- [ ] §2.8.4 The Simulation-to-Real Transfer Problem *(needs 2.8.1, 2.8.3)*
- [ ] §2.7.8 Continuous-Coordinate / Geometry-Agnostic Reconstruction
      *(needs 2.7.1, 2.7.4, 2.7.7, 2.6.5 — **the gap section**; write it once
      you can state precisely what the existing tools assume and cannot do)*
- [ ] §2.9.4 Accessibility and the Case for Low-Cost Architectures

## Wave 4 — synthesis, must be last

Nothing here contains new literature. Each one re-reads what you already wrote.
If a Wave 4 section is hard to write, that is a signal a Wave 1–3 section is
thin — treat it as diagnostic, not as a writing problem.

- [ ] §2.10 Summary and Research Gap *(was §2.11; now also absorbs what was
      §2.9.6 Implications for Low-Cost PET — the ceiling-vs-floor argument and
      software-substituting-for-hardware pattern)*
- [ ] §2.1 Introduction — scope, what is out of scope and why, how the chapter
      builds to the gap, plus a short prose note on how the literature was
      identified *(describes the chapter's final shape, so drafting it earlier
      means rewriting it)*
- [ ] §1.2 Cost Drivers — finish *(unblocked by §2.9.3)*
- [ ] §1.3 Opportunities for Low-Cost PET *(needs §2.10)*
- [ ] §1.4 Aims of This Review
- [ ] §1.5 Candidate Research Directions *(needs the whole review — this is the
      thesis's argument, and the section your supervisor will judge)*
- [ ] §1.6 Thesis Outline *(last; one sentence per chapter)*

---

## Notes

**§2.9 "Contemporary Directions" was cut.** Its six subsections mirrored the
pipeline 1:1 (Modern Approaches to Radiotracers ↔ §2.3, to Scintillators ↔
§2.4, to Photodetectors ↔ §2.5, to Architecture ↔ §2.6, to Reconstruction ↔
§2.7). That meant writing every topic twice — once as "the state of things",
once as "where it's going" — and keeping the two halves consistent for three
years. Each pipeline section now ends with its own forward-look instead, and
§2.9.6 Implications for Low-Cost PET, the only part the pipeline sections
could not do for themselves, moved into §2.10 Summary and Research Gap.
Everything after it renumbered: old §2.10 → §2.9, old §2.11 → §2.10.

**§2.4 was reorganised by material class, not by novelty.** It previously split
"established" from "emerging", a temporal axis that ages badly and grouped
transparent ceramics (inorganic), nanocomposites (hybrid) and plastics
(organic) together purely because they were all recent. Now: mechanisms
(§2.4.1, covering both inorganic band-structure and organic molecular
scintillation), inorganic crystals and ceramics (§2.4.2), organic (§2.4.3),
composites (§2.4.4), then segmentation and DOI. Organic earns its own
subsection because it is the most extreme cost play available, and because
§2.4.1 previously explained only the inorganic mechanism while §2.4.3
introduced plastics with no physics behind them.

**Scope and Review Methodology were cut as separate subsections.** A formal
methodology section (databases, search strings, inclusion/exclusion criteria)
belongs to a *systematic* review, where the search protocol is itself a result.
This chapter is a narrative review organised by topic, so a PRISMA-flavoured
methodology would advertise a rigour the chapter does not practise. The parts
worth keeping — scope, exclusions and their justification, a couple of
sentences on how the literature was found — are now prose under §2.1.

**Check this one with your supervisor before it's final.** Some schools mandate
a methodology section for the confirmation document regardless of review type.
If UTS does, it goes back in and the reasoning above does not apply.

**Chapter 1 is written last despite being first.** Only §1.1 is genuinely
front-loadable, and it is done. Everything from §1.3 on is a conclusion.

**The two "cheap wins" that unblock the most.** §2.9.3 Scanner Cost Structure
unblocks §1.2 and feeds §2.10 and §1.3. §2.6.1 unblocks all of §2.6. Doing
these early in their wave buys disproportionate freedom.

**Wave 1 is ~13 sections of low-risk writing.** If you need to show your
supervisor progress, that is the block to attack — it is defensible, citable,
and none of it gets invalidated by where the project direction lands.
