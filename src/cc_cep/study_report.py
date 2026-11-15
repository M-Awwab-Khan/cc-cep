"""Build factual result inserts and portable trial bundles after the study finishes.

Rendered documents remain review-required; this module never marks the CEP complete.
"""

import csv
import hashlib
import json
import shutil
import subprocess
import tarfile
from pathlib import Path


def _write_digest(path):
    with path.open("rb") as stream:
        value = hashlib.file_digest(stream, "sha256").hexdigest()
    Path(str(path) + ".sha256").write_text(value + "  " + path.name + "\n")
    return value


def export_bundles(directory, original):
    destination = original / "results/evidence" / directory.name
    destination.mkdir(parents=True, exist_ok=True)
    matrix = json.loads((directory / "matrix.json").read_text())
    entries = []
    for job in matrix["jobs"]:
        for attempt in job["attempts"]:
            trial = directory / attempt["directory"]
            archive = destination / (job["id"] + f"-a{attempt['attempt']}.tar.gz")
            if not archive.exists():
                with tarfile.open(archive, "w:gz") as output:
                    for path in sorted(trial.rglob("*")):
                        if path.is_file() and not path.is_symlink():
                            output.add(
                                path, arcname=str(Path("study") / path.relative_to(directory))
                            )
            entries.append({"file": archive.name, "sha256": _write_digest(archive)})
    metadata = destination / "study-metadata.tar.gz"
    with tarfile.open(metadata, "w:gz") as output:
        for path in sorted(directory.iterdir()):
            if (
                path.is_file()
                and not path.is_symlink()
                and path.suffix in {".json", ".jsonl", ".csv", ".png", ".gz", ".txt", ".log"}
            ):
                output.add(path, arcname=str(Path("study") / path.name))
        folders = [
            directory / "input-evidence",
            *directory.glob("safety-*"),
            directory / "recovery-evidence",
        ]
        for folder in folders:
            for path in sorted(folder.rglob("*")):
                if path.is_file() and not path.is_symlink():
                    output.add(path, arcname=str(Path("study") / path.relative_to(directory)))
    entries.append({"file": metadata.name, "sha256": _write_digest(metadata)})
    index = destination / "index.json"
    index.write_text(
        json.dumps(
            {
                "schema": 1,
                "archives": entries,
                "study": directory.name,
                "description": "Every selected and failed attempt, raw observations, source snapshots, and analysis tables",
            },
            indent=2,
        )
        + "\n"
    )
    _write_digest(index)
    return index


def build_report(directory: Path, original: Path):
    matrix = json.loads((directory / "matrix.json").read_text())
    trials = list(csv.DictReader((directory / "trials.csv").open()))
    complete = {row["directory"] for row in trials if row["state"] == "COMPLETE"}
    counts = {
        kind: sum(job["kind"] == kind and job["directory"] in complete for job in matrix["jobs"])
        for kind in ("core", "control", "background")
    }
    text = (
        f"The retained full-duration study contains {counts['core']} verified core comparisons out of 80, "
        f"{counts['control']} no-fault controls out of ten, and {counts['background']} background "
        "ablation runs out of twenty. Every declared trial and retry remains in the manifest. "
        "The corresponding raw outcomes and frozen source are available in checksum-verified bundles.\n\n"
    )
    if matrix.get("recovery_amendment"):
        text += (
            "An explicit post-failure protocol amendment allowed one additional attempt of an "
            "invalid high-load execution after independent full-length no-fault and fault-on "
            "qualification. The original rule allowed only one retry. Two completed comparisons "
            "were carried forward without rerunning them; every invalid attempt remains archived. "
            "The transient cause remains unresolved. Artifact compilation/rendering overlapped "
            "the first retained trial and may have contributed to shared-host interference. "
            "These deviations limit interpretation even when the remaining runs complete.\n\n"
        )
    if matrix.get("qualification_protocol"):
        text += (
            "The replacement comparison uses 32 and 64 requests/s per cohort after two "
            "independent full-length no-fault qualifications at each rate. Admission required "
            "per-stream 99 percent Wilson upper screening bounds below half the SLO bad fractions, no dropped "
            "iterations or pod drift, and explicit CPU headroom. Earlier 48/112 requests/s "
            "studies were superseded after recurrent invalid high-load execution; their "
            "completed trials are not pooled into this comparison and their failed attempts "
            "remain archived. Independent cost pilots at 48 requests/s were retained. "
            "This is a revised workload protocol, not confirmation that the earlier stalls "
            "have a single proven cause.\n\n"
        )
    text += r"""\begin{table*}[width=\textwidth,cols=6,pos=t]
\caption{Closed-loop minus comparator differences in usable-guard overshoot. Intervals use paired run-block bootstrap resampling; negative values favor closed-loop on this metric only.}\label{tbl:paired}
\small
\begin{tabular*}{\tblwidth}{@{\extracolsep{\fill}}lllrll@{}}
\toprule
Fault & Requests/s & SLO & Comparator & Mean difference & 95\% interval \\
\midrule
"""
    for row in csv.DictReader((directory / "paired-comparisons.csv").open()):
        if row["metric"] != "guard_overshoot":
            continue
        if row["complete"] == "True":
            difference = f"{float(row['mean_difference']):.2f}"
            interval = f"[{float(row['ci_low']):.2f}, {float(row['ci_high']):.2f}]"
        else:
            difference = "Incomplete"
            interval = "Unavailable"
        text += f"{row['family']} & {row['rps']} & {row['slo']} & {row['comparator']} & {difference} & {interval} \\\\\n"
    text += r"""\bottomrule
\end{tabular*}
\end{table*}

Full-allocation overshoot, exposure differences, observed failures and empirical costs appear in the accompanying CSV tables. A guard-overshoot improvement alone does not establish a better safety/exposure trade-off. The intervals are descriptive, with only five blocks and no multiplicity adjustment. Any missing pair remains explicitly incomplete rather than disappearing from analysis.

"""
    if (directory / "comparison.png").exists():
        text += r"""\begin{figure*}
\centering
\includegraphics[width=.96\textwidth]{results/curated/study-comparison.png}
\caption{Every verified core run, showing exposure against overshoot of the usable allocation. Full-allocation overshoot is separately retained in the raw tables.}\label{fig:study}
\end{figure*}
"""
    bg_path = directory / "background-comparisons.csv"
    if bg_path.exists():
        text += r"\subsection{Controlled background attribution}\label{sec:background}" + "\n"
        for row in csv.DictReader(bg_path.open()):
            if row["metric"] == "absolute attribution error":
                if row["complete"] == "True":
                    text += (
                        f"At {row['rps']} requests/s, {row['slo']} point-estimate minus naive-total "
                        f"absolute error was {float(row['mean_difference']):.2f} requests "
                        rf"(95\% interval [{float(row['ci_low']):.2f}, {float(row['ci_high']):.2f}]). "
                    )
                else:
                    text += f"The {row['rps']} requests/s {row['slo']} background comparison has incomplete blocks. "
        text += "The reference subtracts tagged synthetic organic failures; incidental non-organic failures and shared-node interference remain possible.\n"
    frozen = directory / "frozen"
    for root in (frozen, original):
        (root / "results/curated").mkdir(parents=True, exist_ok=True)
        (root / "results/curated/study-results.tex").write_text(text)
        if (directory / "comparison.png").exists():
            shutil.copy2(
                directory / "comparison.png", root / "results/curated/study-comparison.png"
            )
    manuscript = frozen / "cas-dc-template.tex"
    source = manuscript.read_text()
    start = source.index("% BEGIN GENERATED STUDY ABSTRACT")
    end = source.index("% END GENERATED STUDY ABSTRACT", start)
    abstract = (
        "% BEGIN GENERATED STUDY ABSTRACT\n"
        "Chaos experiments consume the reliability resources they test. We implement separate request-count availability and latency ledgers, fault-intensity feedback, conditional background credit and an independent cleanup watchdog. Review identified and corrected zero-loss uncertainty charging and non-sticky cleanup failure. "
        f"The retained full-duration dataset contains {counts['core']}/80 verified core comparisons, {counts['control']}/10 controls and {counts['background']}/20 background ablation runs. "
        "We report allocation and usable-guard overshoot separately from fault exposure, with descriptive bootstrap intervals across replication blocks and all failed attempts retained. Source snapshots and raw client outcomes support ledger replay. These results describe the tested single-node benchmark; they establish neither unconditional safety nor general causal validity or first-ever novelty.\n"
    )
    manuscript.write_text(source[:start] + abstract + source[end:])
    original_main = original / "cas-dc-template.tex"
    original_text = original_main.read_text()
    if (
        "% BEGIN GENERATED STUDY ABSTRACT" in original_text
        and "% END GENERATED STUDY ABSTRACT" in original_text
    ):
        begin = original_text.index("% BEGIN GENERATED STUDY ABSTRACT")
        finish = original_text.index("% END GENERATED STUDY ABSTRACT", begin)
        original_main.write_text(original_text[:begin] + abstract + original_text[finish:])
    build = frozen / "results/tmp" / f"{directory.name}-final-report-build"
    build.mkdir(parents=True, exist_ok=True)
    with (build / "compile-console.txt").open("w") as log:
        result = subprocess.run(
            [
                "latexmk",
                "-pdf",
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-outdir=" + str(build),
                "cas-dc-template.tex",
            ],
            cwd=frozen,
            stdout=log,
            stderr=log,
            timeout=240,
        )
    artifact = original / "output/pdf/cep-report-study-draft.pdf"
    if result.returncode == 0:
        artifact.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(build / "cas-dc-template.pdf", artifact)
        (directory / "report-status.json").write_text(
            json.dumps(
                {"compiled": True, "path": str(artifact), "visual_review_required": True}, indent=2
            )
            + "\n"
        )
    else:
        (directory / "report-status.json").write_text(
            json.dumps({"compiled": False, "log": str(build / "compile-console.txt")}, indent=2)
            + "\n"
        )
    export_bundles(directory, original)
