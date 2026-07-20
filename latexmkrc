# latexmk config: pdflatex + bibtex
$pdf_mode   = 1;   # produce PDF via pdflatex
$bibtex_use = 2;   # run bibtex when needed, always use .bib
# keep the worktree clean: aux/log/bbl etc. go to build/, main.pdf stays here
$aux_dir     = 'build';
$emulate_aux = 1;  # TeX Live has no -aux-directory; latexmk moves the files
