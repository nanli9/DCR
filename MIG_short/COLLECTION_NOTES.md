# MIG Short-Paper Corpus — Collection Notes

Built 2026-07-30. Purpose: a set of **real, verified, accepted** ACM SIGGRAPH MIG short-track
papers to rank a submission against the venue's actual short-paper bar.

**Result: 7 papers, 2 years (MIG 2024 and MIG 2025). 5 with full text, 2 abstract-only.**
This is below the 8-15 target. The shortfall is not a search failure — it is a hard limit of
what MIG publishes, explained in "Why the corpus stops at seven" below.

---

## 1. Inclusion rule

A paper is in the corpus **only if a primary conference source explicitly labels it a short
paper**. No paper was included on the basis of page count, topic, or any other inference.

Concretely: both entries in the corpus trace to a per-paper "Short" marker in the official
program page for that year.

| Year | Source | Per-paper long/short labels? |
|---|---|---|
| 2025 | https://mig.siggraph.org/2025/program/ | **Yes** — each paper tagged `Long` / `Short` / `Invited` |
| 2024 | https://sgmig.hosting.acm.org/mig-2024 | **Yes** — each paper tagged `Long \| 15m` or `Short \| 10m` |
| 2023 | https://project.inria.fr/mig2023/ | **No** |
| 2022 | mig2022.cs.purdue.edu | Site unreachable; proceedings TOC has no short section |
| 2021 | https://mig2021.inria.fr/ | **No** (marks `(TVCG Paper)` only) |
| 2019 | MIG '19 proceedings TOC | **No** |

## 2. What was searched, and what worked

**Worked**
- **MIG per-year conference program pages** — the only per-paper track attribution that
  exists anywhere. This is the backbone of the corpus.
- **DBLP**, both the HTML TOC and the JSON API
  (`dblp.org/search/publ/api?q=toc:db/conf/mig/mig2025.bht:`) — gave complete, authoritative
  author lists, DOIs, and ACM page ranges. DBLP does **not** distinguish long from short.
- **Semantic Scholar Graph API** (`api.semanticscholar.org/graph/v1/paper/DOI:<doi>`) — gave
  verbatim abstracts and Unpaywall open-access status for all 7 papers.
- **Open-access mirrors**: HAL (Inria, IP Paris), Politecnico di Torino IRIS, and author
  pages (ETS Montreal; theodoroskyriakou.com). All 5 full texts came from these.

**Did not work**
- **ACM Digital Library** returned HTTP 403 to every automated request — proceedings TOCs,
  `/doi/pdf/`, and `/doi/full/` — including with a browser user-agent, and *including for
  papers Unpaywall marks GOLD / CC-BY*. This is the sole reason 2 of 7 papers are
  abstract-only.
- **mig2022.cs.purdue.edu** — TLS handshake failure; the MIG 2022 site appears to be gone.
- **web.archive.org** — unreachable from this environment / rate-limited.
- No arXiv preprint exists for any of the seven.

## 3. What the MIG short-paper track actually looks like

### Formal rules (identical at MIG 2024 and MIG 2025)

> "4-6 pages for **short papers**, and up to 10 pages in length for **long papers**,
> excluding references"
> — https://mig.siggraph.org/2025/submission/

- **Double-blind** review, anonymous submission with an assigned paper ID.
- "All accepted papers, long and short, will appear in the conference proceedings and
  archived in the ACM Digital Library." Short papers are **archival**, unlike posters, which
  "will not be published in the official MIG proceedings or the ACM Digital Library."
- Authors are actively steered toward the short track: the CFP encourages authors to "submit
  their work as a short paper if the content can fit the 6 page limit (excluding
  references)."
- Presentation slot is shorter: 10 min at MIG 2024 vs 15 min for long. MIG 2023 stated
  "Short papers: 15 mins [10 mins presentation + 5 mins questions]" vs "Full papers: 30 mins
  [20 mins presentation + 10 mins questions]."

### Volume — short papers are a small minority

- **MIG 2025: 4 short out of 19 papers (21%).** Reported acceptance: "15 long and 4 short
  papers (out of 46 total submissions), 11 posters, and 3 invited papers from journals."
- **MIG 2024: 3 short out of 21 papers (14%).**

So a MIG short paper is not a consolation track with a soft bar; in a given year only three
or four exist.

### Length in practice

All four MIG 2025 short papers occupy **exactly 7 pages** in the ACM DL (`3:1-3:7`,
`5:1-5:7`, `11:1-11:7`, `18:1-18:7`) — i.e. authors use the full 6-page body allowance plus
about one page of references. Every long paper that year is 8 pages or more. The MIG 2024
author copies run 6-7 pages. Downloaded PDFs carry roughly **12-33 references**.

### Scope and structure in practice

Every full text in the corpus uses the compressed-full-paper structure: Introduction,
Related Work, Method / Method Overview, Results or Evaluation, Conclusion. None is a position
paper, none is a work-in-progress abstract.

Across the seven, three recognisable shapes:

1. **A focused technical increment on a named prior method**, with a small results section.
   *Adaptive Sub-stepping* adds one heuristic (a diagonalized geometric stiffness matrix) to
   existing rigid-body sub-stepping. *Trajectory-aware Smears* opens by saying outright that
   it extends "the method of Basset et al. [2024]" and delivers the extension "with minor
   computational and memory overheads."
2. **A complete but modest system**, demonstrated rather than benchmarked. *DRUMS* (MIDI to
   full-body drumming) and *Storyboarding in XR* both build a working pipeline and report one
   evaluation, in the XR case a usability test with a Limitations subsection.
3. **A small perceptual or user study answering one question.** *Investigating How Text and
   Motion Style Shape Directness* and the *AR controller* study each run a single study with
   one or two factors, and both report partly negative or mixed results (no significant
   difference in autonomy and competence; NVB mattering only when aligned with indirect
   language).

**What a short paper is expected to deliver here: one contribution, demonstrated once, with
enough related work to place it.** Not a broad benchmark, not an ablation suite, not multiple
independent contributions. Negative and mixed results are publishable. Explicitly framing the
work as an extension of one prior paper is publishable.

## 4. Why the corpus stops at seven

MIG only attributes long-vs-short **per paper** on its 2024 and 2025 program pages. It is
not in the ACM DL proceedings structure, not in DBLP, and not in the published TOC for any
year: MIG proceedings are organised by topical session (e.g. "SESSION: Motion Control and
Planning") plus, in some years, "SESSION: Poster Abstracts". There is no "Short Papers"
section to read off.

For 2023 the program states the short-paper *timing rule* but labels no individual paper.
For 2021 it distinguishes only journal-invited papers. For 2022 the conference site is dead.

MIG 2024 and 2025 together accepted **exactly seven** short papers. The corpus therefore
contains **every MIG short paper that can be identified without guessing**. It is complete
with respect to its own inclusion rule; it is simply that the rule can only reach two years.
Extending to 8+ would require inferring track membership from page counts in years where the
program does not say, which would risk seeding a calibration exercise with mislabelled data.

## 5. Limitations — read before using this corpus

1. **Small n.** Seven papers, two years. Any distributional claim ("typical MIG short paper
   does X") rests on 7 data points, and 3 of the 7 are user/perception studies rather than
   technical-method papers. For a graphics/simulation submission the *directly* comparable
   set is 2 papers (Adaptive Sub-stepping, Trajectory-aware Smears).
2. **Two of seven are abstract-only** (`mig2025_short_eca_directness`,
   `mig2024_short_ar_controller`). Their length, structure, and evaluation depth are unknown
   to this corpus; only their abstracts were verified. Cause: ACM DL 403, no mirror.
3. **Three of five full texts are preprint/repository versions, not the ACM camera-ready.**
   HAL (Trajectory-aware Smears, Expressive Animation Retiming), Politecnico IRIS
   (Storyboarding). Two of those carry a repository cover sheet, counted in `pdf_pages` and
   flagged in the manifest. Content should match the published version; pagination and
   copy-editing may not. `mig2024_short_adaptive_substepping.pdf` is the author's own copy
   from ETS Montreal; `mig2025_short_drums.pdf` is the author project-page copy.
4. **The MIG 2025 acceptance statistic is third-party**, from an Interactive Media Lab
   Dresden news post, not from the organizers. I treat it as corroborated rather than
   primary: it is consistent with an independent DBLP count (19 papers = 15 long + 4 short,
   11 posters and 3 invited papers in the program). No comparable submission count was found
   for MIG 2024, so the 14% figure for that year is an accepted-papers ratio only, not an
   acceptance rate.
5. **Asymmetric verification of the track labels.** For 2025 I cross-checked independently:
   the four papers the program labels `Short` are exactly the four 7-page entries in DBLP,
   and every `Long`-labelled paper is 8+ pages. For 2024 the labels come from a single source
   (the program page); I confirmed the three papers' existence, authors, and DOIs against
   DBLP and Semantic Scholar, but could not re-derive the `Short` marker from a second
   source, because MIG 2024 DBLP entries carry article numbers rather than page ranges.
6. **Program pages were read through a page-summarizing fetch tool**, not raw HTML, because
   the environment could not retrieve those hosts by direct request. Titles, authors, and
   DOIs for all seven were then re-verified against DBLP and Semantic Scholar; the *labels*
   were not independently re-fetched for 2024 (see 5).
7. **One title discrepancy, documented not silently resolved.** The MIG 2024 program lists
   "Controller ratings versus performance in a mobile augmented reality platform game"; the
   ACM/DBLP title is "Controller influence on self-determination versus performance in a
   mobile augmented reality platform game". Same authors, same slot. The published title is
   canonical in the manifest.
8. **Posters and journal-invited papers are excluded.** Posters are explicitly not in the
   proceedings or the ACM DL; invited journal papers are a different track.
9. **No fabrication.** Every abstract in this corpus is a verbatim Semantic Scholar Graph API
   record, cross-checked against the downloaded PDF where one exists. No abstract, author
   list, page count, or result was written, paraphrased, or reconstructed by the collector.
   Where a fact could not be verified it is marked as missing rather than filled in.

## 6. Files

```
MIG_short/
├── corpus_manifest.json                              # one record per paper
├── COLLECTION_NOTES.md                               # this file
└── corpus/
    ├── mig2024_short_adaptive_substepping.pdf / .txt   full text  (6 pp)
    ├── mig2024_short_animation_retiming.pdf   / .txt   full text  (7 pp + HAL cover)
    ├── mig2024_short_ar_controller.abstract.md         abstract only
    ├── mig2025_short_drums.pdf                / .txt   full text  (7 pp)
    ├── mig2025_short_storyboarding_xr.pdf     / .txt   full text  (7 pp + IRIS cover)
    ├── mig2025_short_trajectory_smears.pdf    / .txt   full text  (7 pp + HAL cover)
    └── mig2025_short_eca_directness.abstract.md        abstract only
```

`.txt` files are `pdftotext -layout` extractions of the adjacent PDF, provided for search and
analysis; the PDF is authoritative.
