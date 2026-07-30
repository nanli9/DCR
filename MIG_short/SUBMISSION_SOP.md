# MIG 2026 short-paper submission SOP

Written 2026-07-30. Requirements taken from <https://mig.siggraph.org/2026/papers.htm>
on that date. Re-read the live page before submitting; if it disagrees with this
document, the live page wins.

---

## 0. The dates

| | |
|---|---|
| Submission window | 25 July - **7 August 2026** |
| Notification | 24 September 2026 |
| Camera-ready | 8 October 2026 |
| Timezone | **23:59 AoE (Anywhere on Earth)** for every deadline |

AoE means the deadline passes when it is 23:59 on 7 August in the last timezone on
earth, i.e. **08:59 on 8 August US Eastern / 05:59 Pacific**. Do not plan around that
margin; upload a working version days early and replace it. EasyChair allows updating a
submission until the deadline.

---

## 1. Accounts and prerequisites

1. **EasyChair account.** Submission goes through
   <https://easychair.org/conferences/?conf=mig2026>. If you do not already have an
   EasyChair account, create one first at <https://easychair.org/account/signup>; it is
   free and takes a few minutes (email confirmation required). Do this **before**
   deadline week: account creation occasionally rate-limits under load.
2. **No ACM account is needed to submit.** ACM eRights only enters at camera-ready, if
   the paper is accepted.
3. **Conference registration is not required to submit**, but note the commitment you
   are making: at least one author must register, and **all accepted papers must be
   presented in person**. Confirm someone can travel before submitting.

---

## 2. What you are submitting

Three artifacts. All are built and verified as of 2026-07-30.

| # | What | Path | Size | Notes |
|---|---|---|---|---|
| 1 | **Paper PDF** | `paper/onesweep_short.pdf` | 700 KB | 7 PDF pages: ~5.50 body + references |
| 2 | **Supplementary video** | `benchmarks/paper_fig/out/onesweep_scene_video.mp4` | 7.7 MB | H.264, 1920x1080, 30 fps, 50.2 s, no audio |
| 3 | **Supplementary data/code** | `paper/supplement_onesweep.zip` | 8.0 MB | 105 files: README, SHA256SUMS, code/, data/ |

Total supplementary payload ~15.7 MB against a **200 MB** limit. Comfortable.

### Why the paper is compliant at 7 PDF pages

The CFP limit for short papers is **4-6 pages excluding references**. This paper's body
measures **5.4983 pages** on a column-aware ruler; the References heading begins at the
top of page 6, column 2, and the bibliography runs onto page 7. Body content therefore
occupies under 6 pages and the seventh sheet is references only, which the limit
excludes. If a chair queries the raw page count, that is the explanation.

### Verified state of the PDF

- Document class is exactly what the CFP mandates:
  `\documentclass[sigconf,screen,review,anonymous]{acmart}`
- Anonymous: renders as "Anonymous Author(s)"; zero hits for the author name,
  home-directory paths, username, institutional email, or repository URL, in the
  rendered text **and** in every figure's non-printing text layer.
- Build health: 0 Overfull, 0 LaTeX warnings, 0 undefined references or citations,
  0 errors, all fonts embedded, letter page size.
- Supplement zip: same anonymity scan across all 105 files, zero hits.

---

## 3. The submission sequence, in order

There is a **chicken-and-egg problem** and it is the single most common way people get
this wrong. The CFP requires the assigned paper ID to appear **in the anonymous PDF**,
but the ID does not exist until you create the submission. So the PDF you first upload
cannot have it. The sequence below resolves that.

### Step 1 - Create the submission and obtain the ID

1. Go to <https://easychair.org/conferences/?conf=mig2026> and sign in.
2. Choose the **Short Papers** track. Verify this explicitly; MIG runs several tracks
   (long papers, short papers, posters) and the page limits differ.
3. Fill in title, abstract, keywords, and **all** author details. Author metadata in
   EasyChair is not part of the anonymous PDF and does not break double-blind review;
   enter it completely and accurately.
4. Upload the current `onesweep_short.pdf` as a placeholder so the submission exists.
5. Submit. **EasyChair now displays a submission number.** Record it. That is the paper ID.

### Step 2 - Put the ID into the paper

1. In `paper/onesweep_short.tex`, find line ~789:
   ```latex
   \acmSubmissionID{}% EasyChair submission ID: fill upon assignment; the CFP
   ```
   Fill it: `\acmSubmissionID{1234}` with the real number.
2. Rebuild:
   ```
   cd /Users/nan/Desktop/DCR/paper
   latexmk -pdf -interaction=nonstopmode onesweep_short.tex
   ```
3. **This does not change the layout.** It was measured: filling a four-digit ID moves
   the page ruler by 0.0000, so no length safety margin is needed. Confirm the page
   count is still 7 and the build is still clean anyway.
4. Confirm the ID renders. It appears in the review-mode header.

### Step 3 - Replace the PDF and attach supplementary material

1. In EasyChair, open the submission and use **"Update file"** to replace the PDF with
   the ID-bearing rebuild.
2. Use **"Add attachment"** (or the equivalent supplementary-material control on this
   conference's EasyChair instance) to upload:
   - `onesweep_scene_video.mp4`
   - `supplement_onesweep.zip`
   If the instance permits only one attachment, bundle both into a single archive. Do
   **not** bundle the video inside the code zip by default: reviewers should be able to
   watch it without extracting 8 MB of CSVs.
3. Re-open the submission afterwards and confirm every file is listed and downloadable.
   Download the PDF back from EasyChair and open it: this catches truncated uploads,
   which are silent and common.

### Step 4 - Disclose the companion submission

The paper cites an anonymous companion submission (`companion2026diagnosis`). MIG's rule
is that a paper may not have **previously appeared in, or be currently submitted to, any
other conference or journal**. Two distinct papers to the same venue in the same cycle do
not violate that rule, but the overlap must be visible to the chairs, not just to
reviewers.

Use whatever field EasyChair provides for notes to the chairs, or email the papers chairs
directly, and state plainly: that a companion submission is under review at the same
venue, which results each paper carries, and what is shared between them. The precise
overlap statement is in the paper's Section 4 "Relation to the companion study"
paragraph; reuse that wording. **Do this at submission time, not if asked later.**

---

## 4. Pre-upload verification checklist

Run through this against the exact file you are about to upload.

```
cd /Users/nan/Desktop/DCR/paper

# page count and size
pdfinfo onesweep_short.pdf | grep -E "^Pages|^Page size"

# build health
grep -c Overfull build/onesweep_short.log
grep -c "^LaTeX Warning" build/onesweep_short.log
grep -c undefined build/onesweep_short.log

# anonymity, rendered text AND figure text layers
pdftotext onesweep_short.pdf - | grep -ci "nanli9\|Users/nan\|usc.edu"
pdftotext onesweep_short.pdf - | grep -m1 -i anonymous

# the submission ID is actually present
pdftotext onesweep_short.pdf - | grep -i "submission\|1234"

# fonts embedded (expect no output)
pdffonts onesweep_short.pdf | awk 'NR>2 && $(NF-3)!="yes"{print "NOT EMBEDDED:",$1}'
```

Manual checks that no script catches:

- [ ] Open the PDF and **look at all 7 pages** at 100%. Figures legible, nothing clipped.
- [ ] Track selected in EasyChair is **Short Papers**, not Long Papers or Posters.
- [ ] The submission ID shown in EasyChair matches the one compiled into the PDF.
- [ ] Video plays from a clean download, start to finish.
- [ ] Supplement zip extracts and its README opens.
- [ ] No author name in the EasyChair *title* or *abstract* fields (the abstract is shown
      to reviewers).

---

## 5. After submitting

- EasyChair emails a confirmation. Keep it.
- You may update files until the deadline. Prefer uploading early and refining.
- Do **not** post the paper to arXiv or a personal page during review if you want to
  preserve double-blind integrity. MIG's rule bars concurrent *submission*, and
  preprinting is usually tolerated, but it weakens anonymity in practice. If you plan to
  preprint, check the current MIG policy first.
- Notification 24 September; camera-ready 8 October. Camera-ready means: remove
  `review` and `anonymous` from the document class, add real authors and
  acknowledgements, complete ACM eRights, and add the DOI and CCS concepts.

---

## 6. Open items and risks

1. **`\acmSubmissionID{}` is empty right now.** This is the only known
   non-compliance with the CFP and it cannot be fixed before EasyChair assigns the ID.
   It is Step 2 above.
2. **The companion-paper overlap is undisclosed to the chairs.** The paper text is
   adequate; the disclosure is a submission-form action. Step 4.
3. **Two submissions from one program in one cycle** carries a salami-slicing perception
   risk regardless of compliance. That is a judgment call for the author, not a rule
   violation, and full disclosure is the mitigation.
4. **In-person presentation is mandatory** for accepted papers. Confirm feasibility
   before submitting.
