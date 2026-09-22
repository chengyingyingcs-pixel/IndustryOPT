#!/usr/bin/env python3
import csv
import importlib.util
import json
import math
import sys
from pathlib import Path

from pyomo.environ import ConcreteModel, Constraint, Objective, Var, value


def load_sample_data(instance_dir: Path):
    json_files = sorted(instance_dir.glob("*.json"))
    csv_files = sorted(instance_dir.glob("*.csv"))
    if len(json_files) == 1 and not csv_files:
        data = json.loads(json_files[0].read_text(encoding="utf-8"))
        matrix_files = sorted(instance_dir.glob("*.mtx"))
        if matrix_files and isinstance(data, dict) and "matrix_path" in data:
            path = Path(str(data["matrix_path"]))
            if not path.is_absolute():
                path = instance_dir / path
            data = dict(data)
            data["matrix_path"] = str(path.resolve())
        return data
    if not json_files and not csv_files:
        raise RuntimeError(f"No JSON or CSV data found in {instance_dir}")
    bundle = {path.stem: json.loads(path.read_text(encoding="utf-8")) for path in json_files}
    for path in csv_files:
        with path.open(newline="", encoding="utf-8") as handle:
            bundle[path.stem] = list(csv.DictReader(handle))
    return bundle


def main():
    sample_dir = Path("sample_data")
    model_path = Path("model.py")
    if not sample_dir.is_dir() or not model_path.is_file():
        raise RuntimeError("Expected model.py and sample_data/ in current workspace")

    spec = importlib.util.spec_from_file_location("candidate_model", model_path.resolve())
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "build"):
        raise RuntimeError("model.py must define build(data: dict)")

    data = load_sample_data(sample_dir)
    model = module.build(data)
    if not isinstance(model, ConcreteModel):
        raise RuntimeError(f"build returned {type(model).__name__}, expected ConcreteModel")

    objective_names = [item.name for item in model.component_data_objects(Objective, active=True)]
    if len(objective_names) != 1:
        raise RuntimeError(f"Expected exactly one active Objective, found {objective_names}")

    variables = list(model.component_data_objects(Var, active=True))
    constraints = list(model.component_data_objects(Constraint, active=True))
    objective = model.component_data_objects(Objective, active=True, descend_into=True)
    objective = next(iter(objective))
    objective_value = value(objective.expr)
    if objective_value is not None and not math.isfinite(float(objective_value)):
        raise RuntimeError("Initial objective is not finite")

    result = {
        "ok": True,
        "n_vars": len(variables),
        "n_constraints": len(constraints),
        "objective": objective_names[0],
        "objective_value": float(objective_value) if objective_value is not None else None,
        "integer_vars": sum(item.is_integer() or item.is_binary() for item in variables),
    }
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:
        print(f"VALIDATION ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
