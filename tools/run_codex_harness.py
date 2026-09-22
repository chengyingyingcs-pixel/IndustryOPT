#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


DATASET_DIR = Path("/public/chengyingying/project/industry_mathopt_dataset")
REPO_DIR = DATASET_DIR
PYTHON = Path("/public/chengyingying/conda_envs/inferopt-py311/bin/python")
EVALUATOR = Path(__file__).resolve().parent / "run_eval_gpt56_noann_rerun.py"
WORKSPACE_ROOT = Path("/public/chengyingying/project/industryopt_harness_workspaces")

PROMPT = '''You are being evaluated as a Codex modeling harness.

Work only in the current workspace. Do not inspect parent directories, absolute paths,
environment variables, network resources, hidden reference models, or reference solutions.
Do not modify the input files.

Read statement.md and data_README.md. Implement a general Pyomo model for every instance of
this problem in model.py. The required API is:

    def build(data: dict) -> pyomo.environ.ConcreteModel

Use only Python's standard library and pyomo.environ. Do not invoke a solver inside build().
Do not hard-code values from any particular instance. Multi-file input is keyed by filename stem,
and CSV rows are dictionaries of strings. Use actual identifiers from the data instead of
assuming consecutive integer indices.

Before finishing, inspect model.py for Pyomo reserved component names, invalid indexing,
empty extrema, and constraints that accidentally evaluate to a Python bool. No sample data
or local validation script is provided in this condition; reason from the statement and data
schema, and ensure that model.py is the evaluated artifact. Your final response should
briefly report completion.
'''


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def problem_dirs() -> list[Path]:
    return sorted(path for path in (DATASET_DIR / "domains").iterdir() if path.is_dir())


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assert_workspace_isolated(workspace: Path) -> None:
    dataset_real = DATASET_DIR.resolve()
    workspace_real = workspace.resolve()
    if dataset_real in workspace_real.parents or workspace_real in dataset_real.parents:
        raise RuntimeError(
            f"workspace must be outside dataset tree: {workspace_real} vs {dataset_real}"
        )


def prepare_workspace(problem: Path, workspace: Path, with_annotations: bool) -> None:
    assert_workspace_isolated(workspace)
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)
    shutil.copy2(problem / "nl/statement.md", workspace / "statement.md")
    if with_annotations:
        shutil.copy2(problem / "nl/annotations.md", workspace / "annotations.md")
    shutil.copy2(problem / "data/README.md", workspace / "data_README.md")

    inventory = {
        str(path.relative_to(workspace)): sha256_bytes(path.read_bytes())
        for path in sorted(workspace.rglob("*"))
        if path.is_file()
    }
    (workspace.parent / "input_inventory.json").write_text(
        json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (workspace.parent / "prompt.txt").write_text(PROMPT, encoding="utf-8")
    (workspace.parent / "prompt.sha256").write_text(
        sha256_bytes(PROMPT.encode("utf-8")) + "\n", encoding="utf-8"
    )


def run_generation(
    problem: Path,
    generation_dir: Path,
    workspace_root: Path,
    with_annotations: bool,
) -> dict:
    problem_dir = generation_dir / problem.name
    problem_dir.mkdir(parents=True, exist_ok=True)
    workspace = workspace_root / problem.name / "workspace"
    prepare_workspace(problem, workspace, with_annotations)

    command = [
        "codex", "exec", "--skip-git-repo-check",
        "--dangerously-bypass-approvals-and-sandbox",
        "--model", "gpt-5.6-sol",
        "-c", 'model_reasoning_effort="high"',
        "--json",
        "-C", str(workspace),
        "--output-last-message", str(problem_dir / "response.md"),
        PROMPT,
    ]
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.time()
    with (problem_dir / "events.jsonl").open("w", encoding="utf-8") as events:
        process = subprocess.Popen(
            command,
            stdout=events,
            stderr=subprocess.PIPE,
            text=True,
            cwd=workspace,
            env=os.environ.copy(),
        )
        _, stderr = process.communicate()
    elapsed = time.time() - started
    (problem_dir / "codex_stderr.log").write_text(stderr or "", encoding="utf-8")

    candidate = workspace / "model.py"
    validation = {
        "skipped": True,
        "reason": "validate_model.py is intentionally not provided in this condition",
    }
    if candidate.is_file():
        shutil.copy2(candidate, problem_dir / "model.py")

    record = {
        "problem": problem.name,
        "stage": "with_annotations" if with_annotations else "strict_no_annotations",
        "model": "gpt-5.6-sol",
        "reasoning_effort": "high",
        "prompt_sha256": sha256_bytes(PROMPT.encode("utf-8")),
        "codex_returncode": process.returncode,
        "elapsed_seconds": elapsed,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "validation": validation,
        "candidate_generated": candidate.is_file(),
    }
    (problem_dir / "record.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return record


def run_evaluation(problem: Path, candidate: Path, output_dir: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        str(PYTHON), str(EVALUATOR), str(problem),
        "--from-code", str(candidate),
        "--model", "gpt-5.6-sol",
        "--no-annotations",
        "--timeout", str(timeout),
        "--out", str(output_dir),
    ]
    run_dirs = sorted((output_dir / problem.name / "runs").glob("*"))
    if run_dirs:
        command.extend(["--resume-dir", str(run_dirs[-1])])
    environment = os.environ.copy()
    python_bin = str(PYTHON.parent)
    if python_bin not in environment.get("PATH", "").split(os.pathsep):
        environment["PATH"] = f"{python_bin}{os.pathsep}{environment.get('PATH', '')}"
    environment["PATH"] = f"{Path.home() / '.idaes/bin'}{os.pathsep}{environment['PATH']}"
    environment["LD_LIBRARY_PATH"] = os.pathsep.join(
        path for path in [
            str(PYTHON.parent.parent / "lib"),
            environment.get("LD_LIBRARY_PATH", ""),
        ] if path
    )
    # The evaluator's timeout is per solver, per instance.  Give the enclosing
    # problem-class process enough time for every instance to exercise the
    # evaluator's maximum solver rotation; otherwise one class containing
    # several hard instances can be killed even though each solver is still
    # within the configured protocol.
    instance_count = sum(path.is_dir() for path in (problem / "data").iterdir())
    class_timeout = instance_count * (timeout * 3 + 60) + 600
    return subprocess.run(
        command,
        text=True,
        capture_output=True,
        timeout=class_timeout,
        env=environment,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["noann", "withann", "noann-eval", "withann-eval"])
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--eval-batch-id")
    parser.add_argument("--timeout", type=int, default=7200)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    if args.stage.endswith("-eval"):
        stage = args.stage[: -len("-eval")]
        generation_root = DATASET_DIR / "eval_results/harness_sweep/generations" / args.batch_id
        if not generation_root.is_dir():
            raise FileNotFoundError(generation_root)
        eval_batch_id = args.eval_batch_id or args.batch_id
        output_root = DATASET_DIR / "eval_results/harness_sweep/evals" / eval_batch_id
        for problem in problem_dirs():
            problem_dir = generation_root / problem.name
            record_path = problem_dir / "record.json"
            if not record_path.is_file():
                raise FileNotFoundError(record_path)
            record = json.loads(record_path.read_text(encoding="utf-8"))
            if not record.get("candidate_generated"):
                raise RuntimeError(f"No candidate for {problem.name}")
            candidate = problem_dir / "model.py"
            print(f"EVAL {problem.name}", flush=True)
            process = run_evaluation(problem, candidate, output_root / problem.name, args.timeout)
            (problem_dir / "eval_stdout.log").write_text(process.stdout or "", encoding="utf-8")
            (problem_dir / "eval_stderr.log").write_text(process.stderr or "", encoding="utf-8")
            print(process.stdout[-4000:], flush=True)
            print(process.stderr[-4000:], file=sys.stderr, flush=True)
            if process.returncode not in (0, 1):
                return process.returncode
        return 0

    with_annotations = args.stage == "withann"
    suffix = "withann-pass1" if with_annotations else "strict-noann-pass1"
    if suffix not in args.batch_id:
        raise SystemExit(f"batch id should contain {suffix}")
    generation_dir = DATASET_DIR / "eval_results/harness_sweep/generations" / args.batch_id
    generation_dir.mkdir(parents=True, exist_ok=True)
    selected = problem_dirs()[: args.limit] if args.limit else problem_dirs()

    overall = {
        "batch_id": args.batch_id,
        "dataset_dir": str(REPO_DIR),
        "model": "gpt-5.6-sol",
        "reasoning_effort": "high",
        "with_annotations": with_annotations,
        "pass_semantics": "pass@1, one class-level candidate per problem",
        "prompt_sha256": sha256_bytes(PROMPT.encode("utf-8")),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "problems": {},
    }
    for index, problem in enumerate(selected, 1):
        print(f"GENERATE {index}/{len(selected)} {problem.name}", flush=True)
        record = run_generation(problem, generation_dir, WORKSPACE_ROOT / args.batch_id, with_annotations)
        overall["problems"][problem.name] = record
        (generation_dir / "generation.json").write_text(
            json.dumps(overall, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    overall["finished_at"] = datetime.now(timezone.utc).isoformat()
    (generation_dir / "generation.json").write_text(
        json.dumps(overall, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
