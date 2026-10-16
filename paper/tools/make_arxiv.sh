#!/bin/sh
# Build the arXiv submission (pdfLaTeX + BibTeX, .bbl included) from the
# ChemRxiv/preprint Markdown.  Output: paper/arxiv/KherveSheet_arxiv.zip
set -e
HERE=$(cd "$(dirname "$0")/.." && pwd)
OUT="$HERE/arxiv"; BUILD=$(mktemp -d)
python3 "$HERE/tools/md2tex_preview.py" "$HERE/chemrxiv/KherveSheet_preprint.md" "$BUILD/raw.tex" --preprint
python3 - "$BUILD/raw.tex" "$BUILD/main.tex" <<'PY'
import re, sys
s = open(sys.argv[1]).read()
s = s.replace(r"\usepackage{fontspec}\setmainfont{Helvetica Neue}\setmonofont{Menlo}[Scale=0.85]",
              r"\usepackage[utf8]{inputenc}\usepackage[T1]{fontenc}\usepackage{lmodern}\usepackage[scaled]{helvet}\renewcommand{\familydefault}{\sfdefault}\usepackage{textcomp}")
s = re.sub(r"\\usepackage\[style=authoryear[^\n]*\n\\addbibresource\{[^}]*\}",
           r"\\usepackage[round,authoryear]{natbib}", s)
s = s.replace(r"\parencite{", r"\citep{")
s = s.replace(r"\printbibliography[heading=bibintoc,title=References]",
              r"\bibliographystyle{plainnat}\bibliography{paper}")
s = s.replace("../figures/", "figures/")
# arXiv shows its own banner; drop ours
s = re.sub(r"\{\\small\\color\{gray\} Preprint ---.*?\}\}\n", "", s, count=1)
open(sys.argv[2], "w").write(s)
PY
mkdir -p "$BUILD/figures"
cp "$HERE/paper.bib" "$BUILD/paper.bib"
cp "$HERE/figures/khervesheet_window.png" "$HERE/figures/tio2_ti2p_chart.png" "$HERE/figures/tio2_mc_ratio.png" "$BUILD/figures/"
cd "$BUILD"
pdflatex -interaction=nonstopmode main >/dev/null || true
bibtex main >/dev/null
pdflatex -interaction=nonstopmode main >/dev/null || true
pdflatex -interaction=nonstopmode main > build.log || { grep '^!' build.log; exit 1; }
grep -E "Citation.*undefined|Reference.*undefined" main.log && exit 1 || true
mkdir -p "$OUT"; rm -f "$OUT"/KherveSheet_arxiv.zip
zip -q "$OUT/KherveSheet_arxiv.zip" main.tex main.bbl paper.bib figures/*.png
cp main.pdf "$OUT/KherveSheet_arxiv_preview.pdf"
echo "built: $OUT/KherveSheet_arxiv.zip ($(grep -o 'Output written.*' main.log))"
