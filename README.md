# SLO-Aware Chaos Engineering for Cloud-Native Applications

Cloud Computing Course CEP by Muhammad Awwab Khan (SE-23051) and Muhammad Abyaz Khalid (SE-23053), NED University of Engineering and Technology.

## Current state
Initialized research and implementation workspace. Existing Introduction and Literature Review are preserved. No controller, cluster, experimental results, or verified final research claims exist yet.

## Overleaf
Upload the project source and choose **cas-dc-template.tex** as the Main document in Overleaf settings. Use **pdfLaTeX** and BibTeX with an available current TeX Live release. The manuscript uses Elsevier's two-column CAS class.

Required local files:
- cas-dc-template.tex: manuscript.
- cas-dc.cls and cas-common.sty: original vendor layout files.
- cas-model2-names.bst: bundled bibliography style.
- cas-refs.bib: existing research references.
- thumbnails/cas-email.jpeg: used by the author email footer.

The original vendor README and manifest are retained for provenance; the manifest describes the upstream distribution, including removed examples. Sample PDFs, alternative single-column templates, sample figures, and vendor documentation sources have been removed.

After upload, use Recompile from scratch and inspect the log, bibliography, author notes, and wide comparison table. Local cleanup does not synchronize an existing Overleaf project automatically. No Overleaf account or remote project is connected in this workspace.

## Local PDF build
Install a TeX distribution with latexmk, then run:

~~~powershell
latexmk -pdf -interaction=nonstopmode -halt-on-error cas-dc-template.tex
~~~

Without latexmk, run pdfLaTeX, BibTeX, pdfLaTeX, pdfLaTeX on the manuscript basename.
Do not commit generated PDF/build files. The vendor .cls/.sty/.bst files retain their upstream licenses.

## Project work
- [Agent guidance](AGENTS.md)
- [Complete CEP plan](docs/CEP-PLAN.md)
- [Decisions and assumptions](docs/DECISIONS.md)

The course brief, rubric, deadline, available hardware, and cloud constraints have not been supplied. The plan is provisional until these are mapped.
