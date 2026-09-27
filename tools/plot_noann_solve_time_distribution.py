#!/usr/bin/env python3
"""Plot the no-annotation solve-time distribution from archived evaluation results."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


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
        return "<=1 s"
    if seconds <= 60:
        return "(1,60] s"
    if seconds <= 100:
        return "(60,100] s"
    if seconds <= 1000:
        return "(100,1000] s"
    if seconds < 7200:
        return "(1000,7200) s"
    return ">=7200 s"


def main() -> None:
    records = load_records()
    colors = {
        "<=1 s": "#177E89",
        "(1,60] s": "#2A9D66",
        "(60,100] s": "#68A357",
        "(100,1000] s": "#E9A23B",
        "(1000,7200) s": "#D76B27",
        ">=7200 s": "#B33A3A",
    }
    counts = {
        bucket: sum(runtime_bucket(record["seconds"]) == bucket for record in records)
        for bucket in colors
    }

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
    fig, ax = plt.subplots(figsize=(11.6, 6.5), dpi=180)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#FAFBFC")

    buckets = list(colors)
    heights = [counts[bucket] for bucket in buckets]
    bars = ax.bar(
        buckets,
        heights,
        color=[colors[bucket] for bucket in buckets],
        edgecolor="white",
        linewidth=1.2,
        width=0.72,
        zorder=3,
    )
    for bar, count in zip(bars, heights):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            count + 1.2,
            f"{count}\n({count / len(records):.1%})",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
            color="#30343B",
        )

    ax.set_ylim(0, 76)
    ax.set_yticks(range(0, 71, 10))
    ax.grid(axis="y", color="#D9DEE3", linewidth=0.8, alpha=0.8, zorder=0)
    ax.grid(axis="x", visible=False)
    ax.spines[["top", "right"]].set_visible(False)

    ax.set_title("Histogram of solver runtimes across all 146 instances", loc="left", fontsize=16, pad=18)
    ax.text(
        0,
        1.015,
        "Six runtime ranges; all bars sum to 146 instances",
        transform=ax.transAxes,
        color="#5B6168",
        fontsize=10.5,
    )
    ax.set_xlabel("Solver runtime range", labelpad=12)
    ax.set_ylabel("Number of instances", labelpad=10)
    ax.tick_params(axis="x", labelsize=10.5, pad=7)

    fig.text(
        0.08,
        0.015,
        "Runtime is the selected solver call for 145 instances; Camera-L2 inst_004 uses the "
        "sum of its two infeasible attempts (177.527 s) and is included in (100,1000] s.",
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
