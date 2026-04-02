# KDD Template PDF Build

## Goal
Produce a KDD-compatible PDF after the full manuscript is assembled in the ACM primary article template.

## Minimal steps
1. Create or open an Overleaf project with the ACM article template used for KDD submissions.
2. Copy the body text from `docs/0402/kdd_section1_overleaf.md` into the manuscript source and replace trace notes with final `\cite{...}` commands.
3. Restore or re-export the bibliography source that matches the representative ids in `docs/0402/20260402_KDD风格_研究背景与现状_v2_证据映射.md`.
4. Build with one of the following commands from the LaTeX project root:
   - `latexmk -pdf main.tex`
   - `xelatex main.tex && bibtex main && xelatex main.tex && xelatex main.tex`
5. Verify KDD-specific constraints after compilation: title block, author block, citation style, double-column layout, page limit, and bibliography rendering.

## Current limitation
This repository currently contains a section-level review PDF only; it is not yet a final ACM/KDD-template paper PDF.
