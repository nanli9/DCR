# DCR follow-up — paper

Isolated LaTeX write-up for the passive modal energy-injection follow-up.

This is an **orphan git branch** (`paper`) with **no code** — a linked git *worktree*
checked out at `DCR/paper/`. The code lives on the repo's other branches
(`native-dynamic-constraint`, …), untouched. Switching here never disturbs the code
working tree and vice-versa.

## Build
```
latexmk -pdf main.tex        # pdflatex → bibtex → pdflatex ×2
# or: pdflatex main; bibtex main; pdflatex main; pdflatex main
latexmk -c                   # clean aux files
```

## Layout
```
main.tex           document + preamble (article class; swap to EG/CGF for submission)
references.bib     prior-art bibliography (has "% VERIFY" flags where unconfirmed)
sections/          one .tex per section (00_abstract … 50_conclusion)
figures/           figures (contact_forces.png copied from ../docs/sheldon_report/)
```

## Claim discipline (binding)
See `../docs/novelty_positioning.md` (do/don't list) and `CLAUDE.md` §14
("claims to avoid"), both on the code branch. Do **not** claim "first two-way
rigid–modal coupling" — Zheng & James 2011 have the mechanism. Lead with the
**passivity bound** and the **real-time-AL embedding**.

## Overleaf sync (git bridge)
The branch is git-bridge ready. Create a **blank Overleaf project first** (the bridge
cannot create one), then:
```
git remote add overleaf https://git.overleaf.com/<project-id>
git push overleaf paper:master          # Overleaf's default branch is 'master'
# pull collaborators' edits back:
git pull overleaf master
```
Authenticate with the Overleaf git token (username `git`, token as password).
