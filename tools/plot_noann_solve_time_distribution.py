#!/usr/bin/env python3
"""Plot the no-annotation solve-time distribution from archived evaluation results."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter


DATASET_ROOT = Path("/public/chengyingying/project/industry_mathopt_dataset")
EVAL_ROOT = DATASET_ROOT / "eval_results/harness_sweep/evals"
FULL_BATCH = EVAL_ROOT / (
    "gpt-5.6-sol-high-strict-noann-pass1-rerun-20260921-100452-"
    "timeout7200-sequential-mem32-betterref-fresh-20260922-060813"
)
CAE_BATCH = EVAL_ROOT / (
    "gpt-5.6-sol-high-strict-noann-pass1-cae-pathfix-20260926-100455-"
    "timeout7200-sequential-mem32"
)
CAE_PROBLEMS = {
    "Compute-CAE-SparseLA-LDLSymmetricPivoting",
    "Compute-CAE-SparseLA-LUPivotReordering",
}
TBE_LOG_TIMES = {
    "inst_001": 0.04,
    "inst_002": 0.16,
    "inst_003": 0.30,
    "inst_004": 1.11,
    "inst_005": 432.13,
    "inst_006": 7200.01,
    "inst_007": 7200.01,
    "inst_008": 7200.02,
}
OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "docs/figures/gpt-5.6-sol-noann-solve-time-distribution.png"
)


def load_records() -> list[dict]:
    records: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for root in (FULL_BATCH, CAE_BATCH):
        result_files = sorted(root.glob("**/result.json"))
        if not result_files:
            raise FileNotFoundError(f"No result.json files under {root}")
        for result_file in result_files:
            result = json.loads(result_file.read_text(encoding="utf-8"))
            problem = result["problem"].split("/")[-1]
            if root == FULL_BATCH and problem in CAE_PROBLEMS:
                continue
            if root == CAE_BATCH and problem not in CAE_PROBLEMS:
                continue

            for instance in result["instances"]:
                name = instance["instance"]
                key = (problem, name)
                if key in seen:
                    raise RuntimeError(f"Duplicate instance: {problem}/{name}")
                seen.add(key)

                source = "solve_seconds"
                seconds = instance.get("solve_seconds")
                if problem == "Compute-TBE-MemoryAllocation":
                    seconds = TBE_LOG_TIMES[name]
                    source = "solver_log"
                elif seconds is None:
                    attempts = instance.get("solver_attempts") or []
                    if problem != "CBG-Camera-VideoStabilization-L2" or name != "inst_004":
                        raise RuntimeError(f"Missing solve time: {problem}/{name}")
                    seconds = sum(float(attempt["seconds"]) for attempt in attempts)
                    source = "infeasible_attempt_total"

                records.append(
                    {
                        "problem": problem,
                        "instance": name,
                        "seconds": float(seconds),
                        "source": source,
                    }
                )

    if len(records) != 146:
        raise RuntimeError(f"Expected 146 instances, found {len(records)}")
    return sorted(records, key=lambda record: record["seconds"])


def runtime_bucket(seconds: float) -> str:
    if seconds <= 1:
        return "<= 1 s"
    if seconds <= 60:
        return "1-60 s"
    if seconds <= 600:
        return "60-600 s"
    if seconds < 7200:
        return "600-7200 s"
    return ">= 7200 s"


def format_seconds(value: float, _position: float | None = None) -> str:
    if value < 1:
        return f"{value:g}"
    return f"{value:,.0f}"


def main() -> None:
    records = load_records()
    colors = {
        "<= 1 s": "#177E89",
        "1-60 s": "#2A9D66",
        "60-600 s": "#E9A23B",
        "600-7200 s": "#D76B27",
        ">= 7200 s": "#B33A3A",
    }
    counts = {
        bucket: sum(runtime_bucket(record["seconds"]) == bucket for record in records)
        for bucket in colors
    }

    ranks = list(range(1, len(records) + 1))
    seconds = [record["seconds"] for record in records]
    point_colors = [colors[runtime_bucket(value)] for value in seconds]

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titleweight": "bold",
            "axes.edgecolor": "#5B6168",
            "axes.labelcolor": "#30343B",
            "xtick.color": "#4D535A",
            "ytick.color": "#4D535A",
        }
    )
    fig, ax = plt.subplots(figsize=(12.8, 7.2), dpi=180)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#FAFBFC")

    ax.plot(ranks, seconds, color="#A8AFB7", linewidth=1.1, zorder=1)
    ax.scatter(
        ranks,
        seconds,
        c=point_colors,
        s=31,
        edgecolors="white",
        linewidths=0.45,
        zorder=2,
    )

    proxy_index = next(
        index
        for index, record in enumerate(records)
        if record["source"] == "infeasible_attempt_total"
    )
    ax.scatter(
        [proxy_index + 1],
        [records[proxy_index]["seconds"]],
        marker="D",
        s=80,
        facecolors="white",
        edgecolors="#20252B",
        linewidths=1.6,
        zorder=4,
    )
    ax.annotate(
        "Camera-L2 inst_004\n177.527 s (two infeasible attempts)",
        xy=(proxy_index + 1, records[proxy_index]["seconds"]),
        xytext=(91, 425),
        textcoords="data",
        arrowprops={"arrowstyle": "->", "color": "#343A40", "lw": 1},
        bbox={"boxstyle": "round,pad=0.35", "fc": "white", "ec": "#B8BEC5"},
        fontsize=9,
        ha="left",
    )

    for value, label in ((60, "60 s"), (600, "600 s"), (7200, "7200 s limit")):
        ax.axhline(value, color="#6E747B", linestyle="--", linewidth=0.8, alpha=0.7)
        ax.text(
            1.5,
            value * (1.08 if value < 7200 else 0.78),
            label,
            color="#555B62",
            fontsize=8.5,
            va="bottom" if value < 7200 else "top",
        )

    ax.set_yscale("log")
    ax.set_ylim(0.03, 12500)
    ax.set_xlim(0, 149)
    ax.set_xticks([1, 25, 50, 75, 100, 125, 146])
    ax.set_yticks([0.04, 0.1, 1, 10, 60, 600, 3600, 7200])
    ax.yaxis.set_major_formatter(FuncFormatter(format_seconds))
    ax.grid(axis="y", which="major", color="#D9DEE3", linewidth=0.7, alpha=0.75)
    ax.grid(axis="x", visible=False)
    ax.spines[["top", "right"]].set_visible(False)

    ax.set_title("Solve-time distribution across all 146 instances", loc="left", fontsize=16, pad=18)
    ax.text(
        0,
        1.015,
        "Instances ranked from fastest to slowest; logarithmic runtime axis",
        transform=ax.transAxes,
        color="#5B6168",
        fontsize=10.5,
    )
    ax.set_xlabel("Instance rank (fastest to slowest)", labelpad=10)
    ax.set_ylabel("Solver runtime (seconds, log scale)", labelpad=10)

    legend_handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor=color,
            markeredgecolor="white",
            markersize=7,
            label=f"{bucket}: {counts[bucket]}",
        )
        for bucket, color in colors.items()
    ]
    legend_handles.append(
        Line2D(
            [0],
            [0],
            marker="D",
            color="none",
            markerfacecolor="white",
            markeredgecolor="#20252B",
            markersize=7,
            label="No accepted solution: attempt total",
        )
    )
    ax.legend(
        handles=legend_handles,
        loc="upper left",
        frameon=True,
        framealpha=0.97,
        facecolor="white",
        edgecolor="#D1D6DB",
        ncol=2,
        fontsize=9,
    )

    fig.text(
        0.075,
        0.015,
        "Runtime is the selected solver call for 145 instances; Camera-L2 inst_004 uses the "
        "sum of its two infeasible attempts so every instance is represented.",
        color="#62686F",
        fontsize=8.5,
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    print(f"wrote {OUTPUT}")
    print("bucket counts:", counts)


if __name__ == "__main__":
    main()
