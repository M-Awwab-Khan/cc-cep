"""Render a clearly labelled recorded-trace demonstration; never injects faults."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FFMpegWriter, FuncAnimation

from cc_cep.evidence import verify


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = verify(args.run)
    metadata = json.loads((args.run / "metadata.json").read_text())
    controller = metadata.get("effective_controller", {})
    baseline = json.loads((args.run / "baseline.json").read_text())
    events = [json.loads(line) for line in (args.run / "events.jsonl").read_text().splitlines()]
    origin = baseline["timestamp"]
    times = np.array([0] + [e["snapshot"]["timestamp"] - origin for e in events])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(3, 1, figsize=(12.8, 7.2), gridspec_kw={"height_ratios": [2, 2, 1]})
    fig.subplots_adjust(top=0.79, bottom=0.11, left=0.12, right=0.96, hspace=0.48)
    fig.suptitle(
        "Recorded controller trace: " + summary["family"], fontsize=22, x=0.12, ha="left", y=0.97
    )
    fig.text(
        0.12,
        0.895,
        "Replay of retained experimental observations. This is not a live cluster capture.",
        fontsize=12,
    )
    fig.text(0.12, 0.855, "Run " + summary["run_id"], fontsize=10, color="#52677a")
    curves = []
    for axis, name in zip(axes[:2], ("availability", "latency")):
        values = np.array([0] + [e["ledgers"][name]["enforced"] for e in events])
        allocation = summary["ledgers"][name]["allocation"]
        axis.axhline(allocation, color="#aebbc4", linestyle="--", label="Allocation")
        if "max_rps" in controller and "reserve_seconds" in controller:
            usable = allocation - controller["max_rps"] * controller["reserve_seconds"]
            axis.axhline(usable, color="#c86b35", linestyle=":", label="Usable guard")
        (curve,) = axis.step(
            [], [], where="post", color="#087f8c", linewidth=2.5, label="Enforced debit"
        )
        curves.append((curve, values))
        axis.set(
            xlim=(0, max(times)),
            ylim=(0, allocation * 1.12),
            ylabel=name.capitalize() + "\nbad requests",
        )
        axis.legend(loc="upper left", fontsize=9)
        axis.grid(alpha=0.15)
    initial = 0.1 if summary["policy"] == "static" else 0.005
    intensities = np.array([initial] + [e["next_intensity"] for e in events])
    (line,) = axes[2].step([], [], where="post", linewidth=2.5, color="#132a42")
    axes[2].set(
        xlim=(0, max(times)),
        ylim=(0, 0.115),
        xlabel="Recorded seconds after admission",
        ylabel="Next fault\nfraction",
    )
    label = fig.text(0.73, 0.855, "", fontsize=11)

    def animate(frame):
        boundary = times[-1] * frame / 119
        count = max(1, np.searchsorted(times, boundary, side="right"))
        for curve, values in curves:
            curve.set_data(times[:count], values[:count])
        line.set_data(times[:count], intensities[:count])
        label.set_text(f"Recorded time: {boundary:.1f} s")
        return [line, label] + [curve for curve, _ in curves]

    animation = FuncAnimation(fig, animate, frames=120, interval=1000 / 12, blit=False)
    animation.save(
        args.output,
        writer=FFMpegWriter(fps=12, codec="libx264", extra_args=["-pix_fmt", "yuv420p"]),
    )
    animate(119)
    fig.savefig(args.output.with_suffix(".png"), dpi=120)
    plt.close(fig)
    print(args.output)


if __name__ == "__main__":
    main()
