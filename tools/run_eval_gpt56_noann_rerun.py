#!/usr/bin/env python3
"""端到端建模测评。

把 nl/ 和 data/ 交给大模型，让它写代码建模并求解，然后看解的质量：

  结论一  目标值与 solution/<inst>.json 的 objective 是否一致（相对容差 1e-6）
  结论二  求出的解代回模型逐条验约束，是否真的可行

不比对 x 值 —— 组合优化普遍存在多重最优，比 x 会把正确的模型判错。
x 只存档作诊断，供人工翻看。

用法:
    export CURSOR_API_KEY=...
    python3 tools/eval/run_eval.py domains/<问题名>
    python3 tools/eval/run_eval.py --all --runs 5        # domains/ 全量，不含 examples/
    python3 tools/eval/run_eval.py examples/sudoku --no-annotations

    # 跳过模型调用，直接评测一份现成代码（自测、复跑用）
    python3 tools/eval/run_eval.py examples/optical_network_rwa \
        --from-code examples/optical_network_rwa/code/model.py
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

TOOLS_DIR = Path("/public/chengyingying/project/industry_mathopt_dataset/tools")
REPO_ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))

REL_TOL = 1e-6
ABS_TOL = 1e-6

DEFAULT_MODEL = "composer-2.5"
DEFAULT_SOLVE_TIMEOUT = 900
# worker 每个实例最多轮换几个求解器（solver_order 每类给 2 个，留一档余量）
MAX_SOLVERS_PER_INSTANCE = 3
MAX_RETRIES = 5
# Agent.prompt 偶发挂死（无超时）。不进 SCHEME_FUNCS，改这里不触发方案指纹失效。
MODEL_CALL_TIMEOUT_SEC = 1200
# 求解子进程的地址空间上限（字节）。见 solve_generated 里的注释。
# 当前评测容器的 cgroup 内存上限为 32 GiB；将 worker 地址空间上限与该
# 上限对齐，避免在大规模实例上提前以 10 GiB 截断求解。宿主仍由 cgroup
# 负责保护，建模/求解子进程不能突破容器的 32 GiB 内存预算。
WORKER_MEM_LIMIT = 32 * 1024**3

# 判定结果
PASS = "pass"
FAIL = "fail"
UNJUDGEABLE = "unjudgeable"


class TransientRunError(RuntimeError):
    """这一次调用没拿到可用回复，但重试可能成功。"""


# --------------------------------------------------------------------------
# 输入：把 nl/ 与 data/ 内联进 prompt
#
# 必须内联而不是给工作目录 —— formulation/、code/、solution/ 就是答案，
# 仓库根目录的 AGENTS.md 还会主动告诉 agent tools/ 下有什么。
# --------------------------------------------------------------------------

PROMPT_TEMPLATE = """\
你是运筹优化专家。下面给出一个业务问题的自然语言描述和配套数据，请你建立数学模型并写出可求解的代码。

{sections}
# 你要输出什么

只输出一个 Python 代码块，不要有其他内容。代码块里必须定义一个函数：

```python
def build(data: dict):
    \"\"\"从 data 构建并返回一个 pyomo ConcreteModel。\"\"\"
```

硬性要求：

1. 用 Pyomo 建模，返回 `ConcreteModel`，其中包含决策变量、唯一的 `Objective`、以及全部约束。
2. **不要在 build 里求解**，只负责建模。求解由调用方完成。
3. 所有数值都从 `data` 里读，不许硬编码。
4. `data` 的结构：单个 JSON 文件时就是该文件解析后的内容；多个文件时是一个字典，
   键为文件名去掉扩展名，JSON 值为解析后的对象，CSV 值为 `list[dict[str, str]]`
   （注意 CSV 读出来全是字符串，需要自己转类型）。
5. 只用标准库和 pyomo，不要 pandas、numpy。
"""

SECTION_TEMPLATE = "# {title}\n\n{body}\n\n"


def read_text(path: Path) -> str | None:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8").strip()


def instance_dirs(problem_dir: Path) -> list[Path]:
    data_root = problem_dir / "data"
    if not data_root.is_dir():
        return []
    return sorted(d for d in data_root.iterdir() if d.is_dir())


def _nl_variant(base: Path, lang: str) -> Path:
    """英文平行语料放在同目录的 `<stem>.en.md`。给了 --lang en 但某个问题还没有
    英文件时直接报错，而不是静默退回中文 —— 那会让一次「英文」运行其实混着中文，
    中英对照的差值就没意义了。"""
    if lang == "zh":
        return base
    en = base.with_suffix(f".{lang}.md")
    if not en.exists():
        raise FileNotFoundError(
            f"缺少 {lang} 平行文本：{en}。英文语料目前只覆盖部分数据集，"
            f"见 paper/parallel_corpus.json"
        )
    return en


def build_prompt(problem_dir: Path, with_annotations: bool, lang: str = "zh") -> str:
    sections: list[str] = []

    statement = read_text(_nl_variant(problem_dir / "nl" / "statement.md", lang))
    if statement:
        sections.append(SECTION_TEMPLATE.format(title="业务问题描述", body=statement))

    if with_annotations:
        ann = read_text(_nl_variant(problem_dir / "nl" / "annotations.md", lang))
        if ann:
            sections.append(SECTION_TEMPLATE.format(title="补充说明", body=ann))

    data_readme = read_text(_nl_variant(problem_dir / "data" / "README.md", lang))
    if data_readme:
        sections.append(SECTION_TEMPLATE.format(title="数据说明", body=data_readme))

    insts = instance_dirs(problem_dir)
    if insts:
        # 只给第一个实例的数据作为格式样例。模型要写出能跑通所有实例的通用代码，
        # 给全部实例既浪费 token，也可能诱导它针对具体数值写死。
        sample = insts[0]
        parts = [f"以下是一个实例（`{sample.name}`）的数据文件，供你了解格式。"
                 f"你的代码需要能处理该问题的全部 {len(insts)} 个实例。\n"]
        for f in sorted(sample.iterdir()):
            if f.suffix not in (".json", ".csv"):
                continue
            body = f.read_text(encoding="utf-8").strip()
            if len(body) > 4000:  # 超长数据截断，格式信息足够即可
                body = body[:4000] + "\n... (已截断)"
            lang = "json" if f.suffix == ".json" else "csv"
            parts.append(f"`{f.name}`:\n\n```{lang}\n{body}\n```\n")
        sections.append(SECTION_TEMPLATE.format(title="数据文件", body="\n".join(parts)))

    return PROMPT_TEMPLATE.format(sections="".join(sections))


# --------------------------------------------------------------------------
# 调用模型
# --------------------------------------------------------------------------

# 语言标记不限，因为回复里常先有一个 bash/text 块（比如安装命令），
# 只认 python 会导致后面真正的代码块提取失败
CODE_BLOCK = re.compile(r"```[^\n]*\n(.*?)```", re.S)


def extract_code(response: str) -> str | None:
    """取回复里包含 build( 的最长代码块。"""
    blocks = [b for b in CODE_BLOCK.findall(response) if "def build(" in b]
    if not blocks:
        return None
    return max(blocks, key=len).strip() + "\n"


def resolve_api_key(env_name: str | None = None) -> str | None:
    """找 API key。

    默认读 CURSOR_API_KEY（SDK 自己也读这个）。留出备选名是因为 Cursor 文档提到
    通过 API 传环境变量时名称不能以 CURSOR_ 开头，万一 Dashboard secrets 也有
    同样限制，用别的名字存也能用。
    """
    if env_name:
        return os.environ.get(env_name)
    for name in ("CURSOR_API_KEY", "CURSOR_EVAL_API_KEY", "EVAL_API_KEY"):
        if os.environ.get(name):
            return os.environ[name]
    return None


def _kill_sdk_bridge_children() -> int:
    """杀掉本进程拉起的 cursor-sdk-bridge，避免超时后僵尸 bridge 毒化下一次重试。

    Agent.prompt 跑在不可打断的线程里；超时后线程/bridge 仍活着，同进程再
    submit 往往会再挂死。bridge 是独立子进程，杀掉它能让挂死的 SDK 调用尽快
    失败，并给下一轮重试腾出干净的 IPC。不进 SCHEME_FUNCS。
    """
    import signal

    killed = 0
    me = os.getpid()
    try:
        import psutil  # type: ignore

        for child in psutil.Process(me).children(recursive=True):
            try:
                cmd = " ".join(child.cmdline())
            except Exception:
                cmd = child.name()
            if "cursor-sdk-bridge" not in cmd:
                continue
            try:
                child.terminate()
                killed += 1
            except Exception:
                pass
        # 给一点时间；仍活着的 bridge 再 SIGKILL
        import time as _time

        _time.sleep(0.5)
        for child in psutil.Process(me).children(recursive=True):
            try:
                cmd = " ".join(child.cmdline())
            except Exception:
                cmd = child.name()
            if "cursor-sdk-bridge" not in cmd:
                continue
            try:
                child.kill()
            except Exception:
                pass
        return killed
    except Exception:
        pass

    # 无 psutil 时：扫 /proc，只杀本进程的直接/间接子进程树里的 bridge
    try:
        children = {me}
        # 多轮扩展子进程集合
        for _ in range(6):
            added = False
            for pid_s in os.listdir("/proc"):
                if not pid_s.isdigit():
                    continue
                pid = int(pid_s)
                try:
                    with open(f"/proc/{pid}/stat", encoding="utf-8") as f:
                        # pid (comm) state ppid ...
                        rest = f.read().split(") ", 1)[1]
                        ppid = int(rest.split()[1])
                except Exception:
                    continue
                if ppid in children and pid not in children:
                    children.add(pid)
                    added = True
            if not added:
                break
        targets = []
        for pid in sorted(children - {me}):
            try:
                with open(f"/proc/{pid}/cmdline", "rb") as f:
                    cmd = f.read().decode("utf-8", "replace")
            except Exception:
                continue
            if "cursor-sdk-bridge" not in cmd:
                continue
            targets.append(pid)
        for pid in targets:
            try:
                os.kill(pid, signal.SIGTERM)
                killed += 1
            except Exception:
                pass
        import time as _time

        _time.sleep(0.5)
        for pid in targets:
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception:
                pass
    except Exception:
        pass
    return killed


def call_model(prompt: str, model: str, api_key: str | None = None) -> tuple[str, dict]:
    """调用 Cursor Agent，返回（回复文本, 元信息）。

    用 no-repo cloud agent：给 env 但不给 repos，agent 拿不到任何仓库文件，
    这是排除「读到参考答案」最彻底的做法。

    env 必须显式给。`CloudAgentOptions()` 全默认时 `to_json()` 是 `{}`，会被
    `AgentOptions.to_json()` 的 `_drop_empty` 整个丢掉，发出去的请求里没有 cloud
    字段，SDK 于是在**当前工作目录**起一个 local agent —— 而当前目录正是仓库，
    formulation/、code/、solution/ 全部可读，测评静默变成开卷，还不报任何错。
    只能靠下面的 agent_id 前缀断言拦住。
    """
    from cursor_sdk import (
        Agent,
        AgentOptions,
        AuthenticationError,
        BadRequestError,
        CloudAgentOptions,
        CloudEnvironment,
        ConfigurationError,
        RateLimitError,
    )

    # 这几类错误重试也不会成功，立即失败，别让使用者白等几十秒
    FATAL = (AuthenticationError, ConfigurationError, BadRequestError)

    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

    delay = 4.0
    last_err: Exception | None = None
    res = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            def _prompt_once():
                return Agent.prompt(
                    prompt,
                    AgentOptions(
                        model=model,
                        api_key=api_key,
                        cloud=CloudAgentOptions(env=CloudEnvironment(type="cloud")),
                    ),
                )

            # 不能用 with ThreadPoolExecutor：fut.result 超时后 __exit__ 里
            # shutdown(wait=True) 会永远卡在挂死的 SDK 线程上。
            pool = ThreadPoolExecutor(max_workers=1)
            try:
                fut = pool.submit(_prompt_once)
                try:
                    candidate = fut.result(timeout=MODEL_CALL_TIMEOUT_SEC)
                except FuturesTimeout as exc:
                    # 线程里的 SDK 调用停不掉；先拆 bridge，再让测评重试。
                    n = _kill_sdk_bridge_children()
                    raise TransientRunError(
                        f"模型调用超过 {MODEL_CALL_TIMEOUT_SEC}s 仍未返回"
                        + (f"（已清理 {n} 个 sdk-bridge）" if n else "")
                    ) from exc
            finally:
                pool.shutdown(wait=False, cancel_futures=True)
            # 云端 run 偶尔会 status=error、回复为空地返回。实测服务端 agent 其实
            # 跑完了、代码也写出来了，是取结果这一步掉的。这属于基建抖动，不拦住的话
            # 下游 extract_code 会把它记成「回复里提不出代码」，一次成功的作答被算成
            # 不通过。
            status = str(candidate.status)
            text = candidate.result or ""
            if "finished" not in status.lower() or not text.strip():
                raise TransientRunError(
                    f"run 没返回可用回复（status={status}，回复 {len(text)} 字符）"
                )
            res = candidate
            break
        except RateLimitError as exc:
            last_err = exc
            wait = getattr(exc, "retry_after", None) or delay
            print(f"  限速，{wait:.0f}s 后重试（第 {attempt}/{MAX_RETRIES} 次）")
            time.sleep(wait)
            delay *= 2
        except FATAL as exc:
            raise RuntimeError(f"{type(exc).__name__}: {exc}") from exc
        except Exception as exc:
            last_err = exc
            if attempt == MAX_RETRIES:
                break
            print(f"  调用失败 {type(exc).__name__}，{delay:.0f}s 后重试")
            time.sleep(delay)
            delay *= 2

    if res is None:
        raise RuntimeError(f"调用模型失败，重试 {MAX_RETRIES} 次仍未成功: {last_err}")

    # 云端 agent 的 id 是 bc-<uuid>，本地 agent 是 agent-<uuid>。拿到 agent- 说明
    # 上面的 cloud 配置没生效、这一次跑成了开卷，重试也救不回来，直接终止。
    agent_id = getattr(res, "agent_id", "") or ""
    if not agent_id.startswith("bc-"):
        raise RuntimeError(
            f"agent 不是云端的（agent_id={agent_id!r}），它能读到本地仓库里的 "
            "formulation/、code/、solution/，这一次测评是开卷的，结果作废"
        )

    usage = res.usage
    meta = {
        "run_id": res.id,
        "agent_id": agent_id,
        "runtime": "cloud",
        "status": str(res.status),
        "model": str(res.model),
        "duration_ms": res.duration_ms,
        "tokens": {
            "input": getattr(usage, "input_tokens", None),
            "output": getattr(usage, "output_tokens", None),
            "total": getattr(usage, "total_tokens", None),
        }
        if usage
        else None,
    }
    return res.result or "", meta


# --------------------------------------------------------------------------
# 执行：在子进程里构建并求解，不信它自己报的数字
# --------------------------------------------------------------------------

# 子进程脚本。放在独立进程里跑有两个原因：生成的代码不可信，可能死循环或
# 占满内存；appsi_highs 的 config.time_limit 实测不生效，只能靠进程级超时。
WORKER = r'''
import json, sys, importlib.util, subprocess, time as _time
from pathlib import Path

model_path, inst_dir, out_path, tools_dir, time_limit = sys.argv[1:6]
# 第 6 个参数可选：热启动用的初始解 JSON（{"variables": {...}, "variables_default": 0}）
warm_start_path = sys.argv[6] if len(sys.argv) > 6 else ""
sys.path.insert(0, tools_dir)            # 为了 import verify_solution.load_data
from verify_solution import load_data

spec = importlib.util.spec_from_file_location("generated_model", model_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

model = mod.build(load_data(Path(inst_dir)))

from pyomo.environ import Constraint, Objective, SolverFactory, Var, value

TL = float(time_limit)

# 热启动的初始解：{变量名: 取值}。未列出的变量取 default（稀疏解只列非零项）。
WARM = None
if warm_start_path:
    _ws = json.loads(Path(warm_start_path).read_text())
    WARM = (_ws.get("variables") or {}, _ws.get("variables_default"))


def apply_warm_start(m, warm):
    """把初始解写进模型变量，作为求解器的起点。

    返回成功赋值的变量数。名字对不上的直接跳过 —— 热启动只是给个起点，
    对不上不该让求解失败。
    """
    if not warm:
        return 0
    values, default = warm
    n = 0
    for v in m.component_data_objects(Var, active=True):
        if v.name in values:
            try:
                v.set_value(float(values[v.name]), skip_validation=True)
                n += 1
            except Exception:
                pass
        elif default is not None and not v.fixed:
            try:
                v.set_value(float(default), skip_validation=True)
                n += 1
            except Exception:
                pass
    return n


def classify(model):
    """看模型是什么类型，决定用哪个求解器。

    次数为 None 表示非多项式（含 log、exp 等）。整数变量很关键：IPOPT 会把整数
    静默松弛掉，给出一个偏优的错误答案，所以含整数的非线性问题绝不能交给它。
    """
    degs = [o.expr.polynomial_degree()
            for o in model.component_data_objects(Objective, active=True)]
    degs += [c.body.polynomial_degree()
             for c in model.component_data_objects(Constraint, active=True)]
    nonpoly = any(d is None for d in degs)
    degree = None if nonpoly else max(degs)
    has_int = any(v.is_integer() or v.is_binary()
                  for v in model.component_data_objects(Var, active=True))
    return degree, has_int


def solver_order(degree, has_int):
    """每类给 2 个求解器，互为对照。

    LP/MILP 的备选从 cbc 换成 scip：实测 CBC 在中大型 MILP 上经常时限内合不上
    gap，SCIP 是更强的开源分支定界（MoE 数据集的参考解就是 SCIP 证的最优）。
    MINLP 首选也换成 scip —— bonmin 只保证局部最优，SCIP 对 MINLP 是全局求解器。
    QP/NLP 那一档配 couenne 是因为 ipopt 只保证局部最优，非凸模型上它可能停在
    局部解；couenne 是全局求解器，能补上这一块。代价是它在连续问题上精度较松，
    实测同一个凸 QP 它报 optimal 但目标值比 ipopt 差一点 —— 所以取的是两者中
    更优的那个，而不是谁先返回就用谁。
    """
    if degree is not None and degree <= 1:
        return ["appsi_highs", "scip"]           # LP / MILP
    if has_int:
        return ["scip", "couenne"]               # MINLP
    return ["ipopt", "couenne"]                  # QP / NLP，纯连续


# 求解器的终止容差（相对 gap）。终止条件是「时限到」或「gap 收到这个数」二者先到
# 者为先。HiGHS 的 mip_rel_gap 默认是 1e-4，比判分容差（1e-6）松两个数量级，不显式
# 压下来的话，一个停在 1e-4 gap 的解可能与参考最优差出判分容差，把建模正确的模型
# 判错。SCIP 的 limits/gap 默认是 0（证到精确最优才停），放宽到 1e-6 让它到了判分
# 精度就交卷，不再多花时间。
MIP_REL_GAP = 1e-6

GAP_OPTIONS = {
    "appsi_highs": {
        "threads": 1,
        "mip_rel_gap": MIP_REL_GAP,
        "mip_abs_gap": 1e-6,
    },
    "scip": {"limits/gap": MIP_REL_GAP, "limits/absgap": 1e-6},
}


def solve_appsi(model, name, tl, warm=False):
    from pyomo.contrib.appsi.solvers import Highs
    opt = Highs()
    opt.config.time_limit = tl
    opt.config.load_solution = False
    opt.config.stream_solver = True       # 求解日志走 stdout，由父进程收进 logs/
    # APPSI 的 warmstart 会把模型上的变量取值经 setSolution 交给 HiGHS 当 MIP start
    opt.config.warmstart = bool(warm)
    opt.highs_options = dict(GAP_OPTIONS["appsi_highs"])
    opt.highs_options["time_limit"] = tl
    res = opt.solve(model)
    if res.best_feasible_objective is None:
        return None, str(res.termination_condition), None
    res.solution_loader.load_vars()
    if not integral_ok(model):
        return None, str(res.termination_condition) + "(整数松弛，不采信)", None
    bound = res.best_objective_bound
    return (
        float(res.best_feasible_objective),
        str(res.termination_condition),
        float(bound) if bound is not None else None,
    )


# IPOPT 是局部 NLP 求解器，只对凸问题保证全局最优；非凸模型拿到的可能是局部解。
# intermediateNonInteger 是 CBC 超时时的状态，此时它会留下一个整数松弛点，
# 直接采信会得到一个偏优的假目标值。
NO_SOLUTION = {
    "infeasible", "unbounded", "infeasibleOrUnbounded", "error", "unknown",
    "intermediateNonInteger", "noSolution",
}

# 时限的选项名各家不同，且传错的后果分两种：cbc 收到 max_cpu_time、bonmin 收到
# seconds 会报 Unknown keyword 直接罢工；而 bonmin 收到 max_cpu_time 更坏 —— 它
# 既不报错也不遵守，实测设 5 秒能跑过 90 秒不返回。couenne 三个候选名全不可用，
# 只能靠进程级硬超时兜底。这份表要和 tools/solve_util.py 保持一致。
NATIVE_TIME_OPT = {
    "cbc": "seconds",
    "ipopt": "max_cpu_time",
    "bonmin": "bonmin.time_limit",
    "scip": "limits/time",
}

HARD_TIMEOUT_MARGIN = 30.0


def integral_ok(model, tol=1e-6):
    """整数变量是否真的取到整数。

    求解器超时后可能留下松弛点，终止状态五花八门，逐个枚举不可靠，
    直接验数值最稳。
    """
    for v in model.component_data_objects(Var, active=True):
        if (v.is_integer() or v.is_binary()) and v.value is not None:
            if abs(v.value - round(v.value)) > tol:
                return False
    return True


def solve_legacy(model, name, tl, warm=False):
    opt = SolverFactory(name)
    native = NATIVE_TIME_OPT.get(name)
    if native:
        opt.options[native] = tl
    for key, val in GAP_OPTIONS.get(name, {}).items():
        opt.options[key] = val
    kwargs = {}
    # 走 NL 文件的求解器（scip / ipopt / couenne）：模型上的变量取值会被 NL writer
    # 写进初值段，求解器据此起步，不需要额外开关。声明支持 warmstart 的再显式打开。
    if warm:
        try:
            if opt.warm_start_capable():
                kwargs["warmstart"] = True
        except Exception:
            pass
    try:
        res = opt.solve(
            model, load_solutions=False, tee=True,
            timelimit=tl + HARD_TIMEOUT_MARGIN, **kwargs
        )
    except subprocess.TimeoutExpired:
        return None, "hardTimeout", None
    tc = str(res.solver.termination_condition)
    if tc in NO_SOLUTION:
        return None, tc, None
    model.solutions.load_from(res)
    if not integral_ok(model):
        return None, tc + "(整数松弛，不采信)", None
    obj = float(value(next(model.component_data_objects(Objective, active=True))))
    bound = None
    try:
        for b in (res.problem[0].lower_bound, res.problem[0].upper_bound):
            if b is not None and abs(float(b)) != float("inf"):
                bound = float(b)
                break
    except Exception:
        pass
    return obj, tc, bound


degree, has_int = classify(model)
out = {
    "n_vars": len(list(model.component_data_objects(Var, active=True))),
    "n_cons": len(list(model.component_data_objects(Constraint, active=True))),
    "degree": degree,
    "has_integer": has_int,
}

SENSE = int(next(model.component_data_objects(Objective, active=True)).sense)
out["sense"] = SENSE


def better(a, b):
    """a 是否严格优于 b。SENSE=1 最小化，-1 最大化。"""
    return (a - b) * SENSE < 0


# 同一个实例轮换多个求解器，取最好的结果。目的不是压榨最优值，而是别让一个建模
# 正确的模型因为某个求解器不给力而被判错 —— 实测过同一份 MILP 换个写法，一个
# 求解器 300s 证不出最优、另一个 231s 就证出来了。
#
# 每个求解器都给满 TL，不切分预算 —— 切分会让首选求解器只拿到一半时间，一个本来
# 能在 TL 内证到最优的模型反而被判错，那是把要修的问题引进来了。谁先证到最优就停，
# 所以常见情形只花第一个求解器的时间；最坏情形才是候选数乘 TL。
candidates = solver_order(degree, has_int)
tried = []
attempts = []
missing = []
solved = None
# 当前已知最好解，作为下一个求解器的起点。初值来自外部传入的初始解（A 线里就是
# 提交方的参考解），之后被更好的解替换 —— 轮换到第二个求解器时不必从零重搜。
warm = WARM
for name in candidates:
    slice_tl = TL
    try:
        fn = solve_appsi if name.startswith("appsi_") else solve_legacy
        # 求解器没装和模型建错是两件事。不先探一下 available()，缺 ipopt 会以
        # ApplicationError 的形式混进 tried 里，最后报成「求解器未返回可行解」，
        # 与模型写错同一个 verdict。
        if not name.startswith("appsi_") and not SolverFactory(name).available(
            exception_flag=False
        ):
            missing.append(name)
            tried.append(f"{name}:未安装")
            continue
        # 每份模型都新建，避免上一个求解器的残留值让 integral_ok 读到别人的数；
        # 要热启动就显式把已知最好解写进去，而不是依赖残留。
        trial = mod.build(load_data(Path(inst_dir)))
        n_warm = apply_warm_start(trial, warm)
        t0 = _time.perf_counter()
        obj, tc, bound = fn(trial, name, slice_tl, bool(n_warm))
        dt = _time.perf_counter() - t0
        tried.append(f"{name}:{tc}")
        attempts.append({
            "solver": name, "termination": tc, "objective": obj,
            "bound": bound, "seconds": round(dt, 3), "time_limit": round(slice_tl, 1),
            "warm_started_vars": n_warm,
        })
        if obj is None:
            continue
        proven = tc.endswith("optimal")
        values = {
            v.name: v.value
            for v in trial.component_data_objects(Var, active=True)
            if v.value is not None and abs(float(v.value)) > 1e-9
        }
        cand = (name, obj, tc, bound, dt, proven, values)
        if solved is None or (proven and not solved[5]) or better(obj, solved[1]):
            solved = cand
            # 只有变好了才更新起点；更差的解拿去热启动反而是帮倒忙
            warm = (values, 0)
        if proven:
            break
    except Exception as exc:
        tried.append(f"{name}:{type(exc).__name__}")

out["solvers_tried"] = tried
# 每个求解器的结果都留档，不只留胜出那个。写论文要对比求解器差异，事后重跑成本很高
out["solver_attempts"] = attempts
out["time_limit_per_solver_sec"] = TL

if solved is None:
    out["ok"] = False
    if len(missing) == len(candidates):
        out["no_solver"] = True
        out["reason"] = (
            "环境里没有能解这类模型的求解器，无法评测（需要 "
            + " 或 ".join(candidates)
            + "）"
        )
    else:
        out["reason"] = "求解器未返回可行解（" + ", ".join(tried) + "）"
else:
    name, obj, tc, bound, dt, proven, values = solved
    out["ok"] = True
    out["solver_used"] = name
    out["termination"] = tc
    out["objective"] = obj
    out["bound"] = bound
    out["solve_seconds"] = round(dt, 3)
    out["proven_optimal"] = proven
    # 非线性问题只能保证局部最优，凸性无法自动判定
    out["local_only"] = name in ("ipopt", "bonmin", "couenne")
    out["variables"] = values

Path(out_path).write_text(json.dumps(out))
'''


def solve_generated(
    model_path: Path,
    inst_dir: Path,
    timeout: int,
    log_path: Path | None = None,
    warm_start_path: Path | None = None,
) -> dict:
    """在子进程里构建并求解生成的模型。

    log_path 给了的话，把子进程的 stdout/stderr 原样写进去。里面是求解器自己的
    日志（appsi_highs 开了 stream_solver、legacy 求解器开了 tee），出错时还有
    traceback。留档是为了事后能查「为什么这个实例超时」而不必重跑。

    timeout 是**每个求解器**的时限。worker 会轮换最多 MAX_SOLVERS_PER_INSTANCE 个
    求解器，所以进程级硬超时按这个倍数放宽 —— 它防的是生成代码死循环，不该在
    worker 正常轮换求解器时把它杀掉。
    """
    hard_timeout = timeout * MAX_SOLVERS_PER_INSTANCE + 60
    with tempfile.TemporaryDirectory() as tmp:
        worker = Path(tmp) / "worker.py"
        worker.write_text(WORKER)
        out = Path(tmp) / "out.json"
        # idaes 装的 ipopt / bonmin / couenne 在 ~/.idaes/bin，不在默认 PATH 上
        env = dict(os.environ)
        extra = Path.home() / ".idaes" / "bin"
        if extra.is_dir():
            env["PATH"] = f"{extra}:{env.get('PATH', '')}"

        # 给子进程设地址空间上限：超大模型（Microgrid 500 万变量级）曾把 15GB 内存
        # 吃满、直接把整台 VM 打挂重启，比一次失败的实例贵得多。上限内 malloc 失败
        # 只会让这个 worker 死掉，记成「子进程失败」，其余实例照跑。
        def _limit_memory():
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (WORKER_MEM_LIMIT, WORKER_MEM_LIMIT))

        argv = [
            sys.executable, str(worker), str(model_path), str(inst_dir),
            str(out), str(TOOLS_DIR), str(timeout),
        ]
        if warm_start_path is not None:
            argv.append(str(warm_start_path))
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=hard_timeout,
                env=env,
                preexec_fn=_limit_memory,
            )
        except subprocess.TimeoutExpired as exc:
            # 进程级超时也要留日志，否则最难查的那一类失败恰恰什么都看不到
            if log_path is not None:
                write_log(log_path, exc.stdout, exc.stderr,
                          f"子进程被硬超时杀掉（>{hard_timeout}s）")
            return {"ok": False, "reason": f"超时（>{hard_timeout}s）"}

        if log_path is not None:
            write_log(log_path, proc.stdout, proc.stderr, f"exit {proc.returncode}")

        if out.is_file():
            return json.loads(out.read_text())

        err = (proc.stderr or proc.stdout or "").strip().splitlines()
        tail = " | ".join(err[-3:]) if err else "无输出"
        return {"ok": False, "reason": f"子进程失败（exit {proc.returncode}）: {tail}"}


def write_log(path: Path, stdout, stderr, tail_note: str) -> None:
    def decode(x):
        if x is None:
            return ""
        return x if isinstance(x, str) else x.decode("utf-8", "replace")

    parts = [decode(stdout)]
    err = decode(stderr).strip()
    if err:
        parts.append(f"\n----- stderr -----\n{err}\n")
    parts.append(f"\n----- {tail_note} -----\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(parts), encoding="utf-8")


# --------------------------------------------------------------------------
# 结论二：可行性 —— 把解代回模型逐条验约束
# --------------------------------------------------------------------------

def check_feasibility(model_path: Path, inst_dir: Path, solved: dict) -> tuple[bool, list[str]]:
    """复用 verify_solution 的逐条代入逻辑。

    挡的是：没真求解就报个数、求解器返回 infeasible 却照样输出、
    解里有变量没赋值、目标值与解不自洽。
    """
    import importlib.util

    from verify_solution import (
        assign_variables,
        check_constraints,
        check_domains,
        check_objective,
        load_data,
    )
    from pyomo.environ import Var

    spec = importlib.util.spec_from_file_location("regen_model", model_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    model = mod.build(load_data(inst_dir))
    issues = assign_variables(model, solved["variables"], default=0)

    if any(v.value is None for v in model.component_data_objects(Var, active=True)):
        return False, issues or ["有变量未赋值"]

    issues += check_domains(model)
    con_issues, _ = check_constraints(model)
    issues += con_issues
    obj_issues, _ = check_objective(model, float(solved["objective"]))
    issues += obj_issues
    return not issues, issues


def check_against_reference(
    problem_dir: Path, inst_dir: Path, solved: dict
) -> tuple[bool | None, list[str], int | None]:
    """把生成模型求出的解代入参考模型验可行。

    这一层挡的是「漏了一条约束、但最优目标值碰巧与参考一致」。实测能发生：
    去掉 RWA 的 C3（同链路同波长互斥）之后，目标值仍是 9，解在它自己的模型里
    也自洽，但 D1 与 D4 同时占用了 L19 的波长 2 —— 只有代入参考模型才看得出来。

    障碍是变量命名可能完全不同（弧变量 vs 路径变量）。所以做成机会主义的：
    两个方向上只要看出「建模方式不同」，就返回 None 表示未验证，而不是误判为
    不可行。

    - 正向：生成解里出现了参考模型没有的变量名；
    - 反向：参考模型里的某族变量在生成解里**整族**缺失。把辅助变量代换掉是合法
      且常见的手法（JPEG 量化表把 `Q[k]` 用 `x[k,c]` 线性表出后不再建 `Q`；MoE
      只在某个分支下才建 `y[l,e]`）。这些变量按 default=0 代进参考模型，只要下界
      大于 0 就会报出一条根本不存在的违反，把正确模型判成 fail —— 2026-08-18 那轮
      全量测评的 512 个实例次里，36 条「代入参考模型不可行」全是这么来的，其中 30
      条因此判错（见 eval_reports/summary_reports/判据复判-20260821-128实例/）。

    只有整族缺失才算「建模方式不同」。同一族里缺几个成员是稀疏建模（未建的组合
    等价于 0），照旧按 0 代入。
    """
    import importlib.util

    from verify_solution import (
        assign_variables,
        check_constraints,
        check_domains,
        load_data,
    )
    from pyomo.environ import Objective, Var

    ref_code = problem_dir / "code" / "model.py"
    if not ref_code.is_file():
        return None, ["参考模型不存在，无法交叉验证"], None

    spec = importlib.util.spec_from_file_location("reference_model", ref_code)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ref_model = mod.build(load_data(inst_dir))
    objectives = list(ref_model.component_data_objects(Objective, active=True))
    ref_sense = int(objectives[0].sense) if len(objectives) == 1 else None

    ref_vars = list(ref_model.component_data_objects(Var, active=True))
    ref_names = {v.name for v in ref_vars}
    gen_names = set(solved["variables"])
    unknown = gen_names - ref_names
    if unknown:
        preview = ", ".join(sorted(unknown)[:3])
        return None, [
            f"变量命名与参考模型不一致（如 {preview}），建模方式不同，无法交叉验证"
        ], ref_sense

    families: dict[str, set[str]] = {}
    for v in ref_vars:
        families.setdefault(v.parent_component().name, set()).add(v.name)
    missing = sorted(fam for fam, names in families.items() if not (names & gen_names))
    if missing:
        preview = ", ".join(missing[:3])
        return None, [
            f"参考模型的变量 {preview} 在生成解里整族缺失（多半是被代换掉了），"
            f"建模方式不同，无法交叉验证"
        ], ref_sense

    assign_variables(ref_model, solved["variables"], default=0)
    issues = check_domains(ref_model)
    con_issues, _ = check_constraints(ref_model)
    issues += con_issues
    return not issues, issues, ref_sense


# --------------------------------------------------------------------------
# 结论一：目标值比对
# --------------------------------------------------------------------------

def close(a: float, b: float) -> bool:
    return abs(a - b) <= max(ABS_TOL, REL_TOL * max(abs(a), abs(b)))


def better_with_tolerance(candidate: float, reference: float, sense: int) -> bool:
    """候选是否在评分容差之外严格优于参考值。

    Pyomo 的目标方向取值为 1（最小化）或 -1（最大化）。落在与目标匹配相同的
    绝对/相对容差内时视为持平，而不是把数值噪声算作改进。
    """
    tolerance = max(
        ABS_TOL,
        REL_TOL * max(abs(candidate), abs(reference)),
    )
    return (candidate - reference) * sense < -tolerance


def no_worse_with_tolerance(candidate: float, reference: float, sense: int) -> bool:
    """候选是否不劣于参考值（严格更优或在评分容差内持平）。"""
    return close(candidate, reference) or better_with_tolerance(candidate, reference, sense)


def load_reference(problem_dir: Path, inst_id: str) -> dict | None:
    path = problem_dir / "solution" / f"{inst_id}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def judge_instance(
    problem_dir: Path,
    inst_dir: Path,
    model_path: Path,
    timeout: int,
    log_path: Path | None = None,
    solution_path: Path | None = None,
) -> dict:
    """判一个实例。

    status == optimal 的参考解按目标匹配判定。对 feasible/heuristic 参考解，实例仍然
    可判定：候选通过可行性门、目标方向一致，且目标严格优于或在评分容差内等于参考值时
    通过；候选更差时失败。只有缺少参考目标或目标方向等无法比较的实例才不可判定。
    """
    inst_id = inst_dir.name
    entry: dict = {"instance": inst_id}

    ref = load_reference(problem_dir, inst_id)
    if ref is None:
        entry.update(verdict=UNJUDGEABLE, reason="没有参考解")
        return entry

    ref_status = ref.get("status")
    entry["reference_status"] = ref_status
    entry["reference_objective"] = ref.get("objective")
    ref_obj = ref.get("objective")
    judgeable = ref_obj is not None
    if not judgeable:
        entry["unjudgeable_reason"] = "参考解没有目标值，无法比较"

    solved = solve_generated(model_path, inst_dir, timeout, log_path)
    entry["termination"] = solved.get("termination")
    entry["n_vars"] = solved.get("n_vars")
    entry["n_cons"] = solved.get("n_cons")
    for k in (
        "solver_used", "degree", "has_integer", "local_only", "solvers_tried", "sense",
        "solve_seconds", "solver_attempts", "time_limit_per_solver_sec", "proven_optimal",
    ):
        if k in solved:
            entry[k] = solved[k]

    if not solved.get("ok"):
        reason = solved.get("reason", "求解失败")
        # 求解器压根没装，这是环境没配好，评不了这个模型，与「模型建错」无关。
        # 记成 fail 会让一个 QP 数据集在缺 ipopt 的机器上 100% 不通过，读报告的人
        # 会以为是模型的问题。
        if solved.get("no_solver"):
            entry.update(
                verdict=FAIL if judgeable else UNJUDGEABLE,
                no_solver=True,
                reason=reason,
            )
            return entry
        # 求解器在时限内没找到可行解，不代表模型建错了，单独标记以便报告里区分
        entry["solver_timeout"] = "maxTimeLimit" in str(solved.get("termination", "")) or "超时" in reason
        if judgeable:
            entry.update(verdict=FAIL, reason=reason)
        else:
            entry.update(verdict=UNJUDGEABLE, reason=f"{entry['unjudgeable_reason']}；且{reason}")
        return entry

    entry["objective"] = solved["objective"]
    # 记下对偶界。termination 是 maxTimeLimit 时 objective 只是可行解不是最优解，
    # 没有界就说不清「差多少」到底是模型建错还是没搜完
    entry["bound"] = solved.get("bound")

    # 解本身不参与判定（组合优化普遍多重最优，比 x 会把正确模型判错），只存档
    # 供人工翻看路径/排产是否合理
    if solution_path is not None:
        solution_path.parent.mkdir(parents=True, exist_ok=True)
        solution_path.write_text(
            json.dumps(
                {
                    "instance": inst_id,
                    "objective": solved["objective"],
                    "bound": solved.get("bound"),
                    "termination": solved.get("termination"),
                    "solver_used": solved.get("solver_used"),
                    "sense": solved.get("sense"),
                    "variables_default": 0,
                    "variables": solved["variables"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    # 结论二：可行性。先在它自己的模型里验，再尝试代入参考模型交叉验证
    try:
        feasible, issues = check_feasibility(model_path, inst_dir, solved)
    except Exception as exc:
        feasible, issues = False, [f"可行性校验异常 {type(exc).__name__}: {exc}"]
    entry["feasible"] = feasible
    if issues:
        entry["feasibility_issues"] = issues[:5]

    try:
        ref_ok, ref_issues, ref_sense = check_against_reference(problem_dir, inst_dir, solved)
    except Exception as exc:
        ref_ok, ref_issues, ref_sense = (
            None,
            [f"交叉验证异常 {type(exc).__name__}: {exc}"],
            None,
        )
    entry["feasible_in_reference"] = ref_ok
    entry["reference_objective_sense"] = ref_sense
    if ref_issues:
        entry["reference_issues"] = ref_issues[:5]
    if ref_ok is False:
        feasible = False
        entry["feasible"] = False

    # 结论一：目标值
    if ref_obj is not None:
        entry["objective_matched"] = close(float(solved["objective"]), float(ref_obj))

    if ref_obj is None:
        candidate_sense = solved.get("sense")
        entry["candidate_objective_sense"] = candidate_sense
        entry.update(verdict=UNJUDGEABLE, reason=entry["unjudgeable_reason"])
    elif not feasible:
        detail = (entry.get("reference_issues") or entry.get("feasibility_issues") or [""])[0]
        where = "代入参考模型后不可行" if ref_ok is False else "解不可行"
        entry.update(verdict=FAIL, reason=f"{where}：{detail}" if detail else where)
    elif ref_sense not in (-1, 1):
        entry.update(
            verdict=UNJUDGEABLE,
            reason="无法确定参考模型目标方向，无法比较候选与参考目标",
        )
    elif solved.get("sense") != ref_sense:
        entry.update(
            verdict=UNJUDGEABLE,
            reason=(
                f"候选与参考模型目标方向不一致（候选 {solved.get('sense')}，"
                f"参考 {ref_sense}）"
            ),
        )
    elif ref_status == "optimal" and not entry["objective_matched"]:
        entry.update(
            verdict=FAIL,
            reason=f"目标值不一致：{solved['objective']:.9g} vs 参考 {float(ref_obj):.9g}",
        )
    elif ref_status != "optimal" and not no_worse_with_tolerance(
        float(solved["objective"]), float(ref_obj), ref_sense
    ):
        entry.update(
            verdict=FAIL,
            reason=(
                f"候选目标劣于非最优参考：{float(solved['objective']):.9g} vs "
                f"参考 {float(ref_obj):.9g}"
            ),
        )
    else:
        if ref_status != "optimal":
            entry["passed_by_better_than_nonoptimal_reference"] = better_with_tolerance(
                float(solved["objective"]), float(ref_obj), ref_sense
            )
            entry["reason"] = (
                f"候选目标不劣于非最优参考：{float(solved['objective']):.9g} vs "
                f"参考 {float(ref_obj):.9g}"
            )
        entry["verdict"] = PASS
    return entry


def _cached_solved_from_solution(solution_path: Path) -> dict | None:
    """读 runs/.../solutions/<inst>.json 成 solve_generated 同形的 dict；不进方案指纹。"""
    try:
        cached = json.loads(solution_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(cached, dict):
        return None
    if cached.get("objective") is None or not isinstance(cached.get("variables"), dict):
        return None
    return {
        "ok": True,
        "objective": cached["objective"],
        "bound": cached.get("bound"),
        "termination": cached.get("termination"),
        "solver_used": cached.get("solver_used"),
        "sense": cached.get("sense"),
        "variables": cached["variables"],
        "resumed": True,
    }


def judge_instance_resuming(
    problem_dir: Path,
    inst_dir: Path,
    model_path: Path,
    timeout: int,
    log_path: Path | None = None,
    solution_path: Path | None = None,
) -> dict:
    """续跑入口：有完整缓存解则跳过求解，否则走正常 judge_instance。

    刻意不进 SCHEME_FUNCS——只影响「中断后续跑」，不该让方案指纹失效。
    """
    if solution_path is not None and solution_path.is_file():
        cached = _cached_solved_from_solution(solution_path)
        if cached is not None:
            # 复用 judge_instance 的后半段：临时把 solve_generated 换成返回缓存。
            # 用闭包注入，避免改动指纹覆盖的 judge_instance 源码。
            real_solve = solve_generated

            def _fake_solve(model_path, inst_dir, timeout, log_path=None):
                print(f"    {inst_dir.name}: 复用已有解（跳过求解）")
                return cached

            # 在本模块命名空间临时替换（脚本以 __main__ 运行时也成立）
            g = globals()
            g["solve_generated"] = _fake_solve
            try:
                return judge_instance(
                    problem_dir, inst_dir, model_path, timeout, log_path, solution_path
                )
            finally:
                g["solve_generated"] = real_solve
    return judge_instance(
        problem_dir, inst_dir, model_path, timeout, log_path, solution_path
    )


# --------------------------------------------------------------------------
# 单次运行
# --------------------------------------------------------------------------

def run_once(
    problem_dir: Path,
    out_dir: Path,
    *,
    model: str,
    with_annotations: bool,
    from_code: Path | None,
    timeout: int,
    api_key: str | None = None,
    fingerprint: dict | None = None,
    resume: bool = False,
    skip_instances: set[str] | None = None,
    lang: str = "zh",
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    gen_dir = out_dir / "generated"
    gen_dir.mkdir(exist_ok=True)
    model_path = gen_dir / "model.py"

    record: dict = {
        "problem": str(problem_dir.relative_to(REPO_ROOT)),
        "model": model,
        "with_annotations": with_annotations,
        "worker_memory_limit_bytes": WORKER_MEM_LIMIT,
        "nonoptimal_reference_policy": "judgeable_pass_if_not_worse_and_feasible",
        # 题面语言。中英是两组独立结果，不记下来就只能靠翻 prompt.txt 猜。
        "lang": lang,
        "started_at": datetime.now(timezone.utc).isoformat(),
        # 记下产物目录，汇总索引靠它生成指向本次运行的链接
        "run_dir": out_dir.name,
        "dataset_dir": problem_dir.name,
        # 指纹存进来，下次 --incremental 才有依据判断这份结果还算不算数
        "fingerprint": fingerprint or {},
    }

    if from_code is not None:
        src = from_code.resolve()
        dst = model_path.resolve()
        if src != dst:
            shutil.copy(from_code, model_path)
        record["source"] = f"--from-code {from_code}"
        print(f"  直接使用现成代码 {from_code}")
    else:
        prompt = build_prompt(problem_dir, with_annotations, lang)
        (out_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
        print(f"  调用 {model}（prompt {len(prompt)} 字符）")
        response, meta = call_model(prompt, model, api_key)
        (out_dir / "response.md").write_text(response, encoding="utf-8")
        record["call"] = meta

        code = extract_code(response)
        if code is None:
            record.update(verdict=FAIL, reason="回复里没有包含 build( 的 Python 代码块")
            (out_dir / "result.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print("  [失败] 回复里提不出代码")
            return record
        model_path.write_text(code, encoding="utf-8")

    insts = instance_dirs(problem_dir)
    sol_dir = out_dir / "solutions"
    log_dir = out_dir / "logs"

    entries = []
    skip_instances = skip_instances or set()
    judge_fn = judge_instance_resuming if resume else judge_instance
    for inst_dir in insts:
        if inst_dir.name in skip_instances:
            ref = load_reference(problem_dir, inst_dir.name)
            ref_status = (ref or {}).get("status")
            judgeable = ref_status == "optimal"
            reason_base = (
                f"参考解 status 为 {ref_status}，不是最优，不能当标准答案"
                if ref and not judgeable
                else "按 --skip-instances 跳过求解（已知会 MemoryError 拖挂机器）"
            )
            entry = {
                "instance": inst_dir.name,
                "reference_status": ref_status,
                "reference_objective": (ref or {}).get("objective"),
                "verdict": UNJUDGEABLE if not judgeable else FAIL,
                "reason": reason_base if not judgeable else (
                    "按 --skip-instances 跳过求解（已知会 MemoryError 拖挂机器）"
                ),
                "skipped_solve": True,
            }
            if not judgeable:
                entry["unjudgeable_reason"] = reason_base
            entries.append(entry)
            mark = {PASS: "通过", FAIL: "不通过", UNJUDGEABLE: "不可判定"}[entry["verdict"]]
            print(f"    {inst_dir.name}: {mark} （--skip-instances）")
            continue
        entry = judge_fn(
            problem_dir,
            inst_dir,
            model_path,
            timeout,
            log_path=log_dir / f"{inst_dir.name}.log",
            solution_path=sol_dir / f"{inst_dir.name}.json",
        )
        entries.append(entry)
        mark = {PASS: "通过", FAIL: "不通过", UNJUDGEABLE: "不可判定"}[entry["verdict"]]
        detail = entry.get("reason", "")
        obj = entry.get("objective")
        obj_txt = f"目标值 {obj:.9g}" if obj is not None else ""
        print(f"    {entry['instance']}: {mark} {obj_txt} {detail}".rstrip())

    record["instances"] = entries
    judgeable = [e for e in entries if e["verdict"] != UNJUDGEABLE]
    passed = [e for e in judgeable if e["verdict"] == PASS]
    record["summary"] = {
        "total": len(entries),
        "judgeable": len(judgeable),
        "passed": len(passed),
        "passed_by_better_than_nonoptimal_reference": sum(
            bool(e.get("passed_by_better_than_nonoptimal_reference")) for e in entries
        ),
        "reference_optimal": sum(e.get("reference_status") == "optimal" for e in entries),
        "unjudgeable": len(entries) - len(judgeable),
        "pass_rate": (len(passed) / len(judgeable)) if judgeable else None,
    }
    record["finished_at"] = datetime.now(timezone.utc).isoformat()

    (out_dir / "result.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return record


# --------------------------------------------------------------------------

def discover_problems(include_examples: bool = False) -> list[Path]:
    """`--all` 要测哪些问题。

    默认只测 `domains/`。`examples/` 下的 `optical_network_rwa` 与 `sudoku` 是演示
    格式怎么填的参考样例，不是数据集本体（`STATUS.md` 的进度表同样不统计它们），
    把它们算进全量测评会让通过率既贵又失真 —— sudoku 每一轮都是 8/8，纯粹在抬高
    分母上的好看程度。要单独跑它们（比如验证判定逻辑的改动，sudoku 是最便宜的一个）
    给个目录路径，或者加 `--include-examples`。
    """
    roots = ("domains", "examples") if include_examples else ("domains",)
    found = []
    for root in roots:
        base = REPO_ROOT / root
        if base.is_dir():
            # rglob 拿到的是 <问题>/code/model.py，往上两级才是问题目录
            found += [p.parent.parent for p in base.rglob("code/model.py")]
    return sorted(found)


def format_summary(records: list[dict]) -> str:
    lines = [
        "| 问题 | 模型 | annotations | 实例 | 可判定 | 通过 | 通过率 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in records:
        s = r.get("summary")
        if s is None:
            lines.append(
                f"| {r['problem']} | {r['model']} | - | - | - | - | 运行失败：{r.get('reason', '')} |"
            )
            continue
        rate = "-" if s["pass_rate"] is None else f"{s['pass_rate'] * 100:.0f}%"
        ann = "含" if r["with_annotations"] else "不含"
        lines.append(
            f"| {r['problem']} | {r['model']} | {ann} | {s['total']} "
            f"| {s['judgeable']} | {s['passed']} | {rate} |"
        )
    return "\n".join(lines)


INDEX_HEADER = """\
# 测评运行索引

每跑一次 `tools/eval/run_eval.py` 追加一行，最新的在最下面。这是所有运行的流水账，
逐个数据集的判读见各自目录下的 `report.md`。

「误差」是该次运行中所有实例里目标值与参考解相差最大的那个；实例之间不可判定
（参考解不是 `optimal`）的不计入。「耗时」是求解那一步的墙钟时间，均值 / 最长值，
不含建模与代回验证。`agent` 是云端 agent id 的前缀，`bc-` 开头才是闭卷。

| 时间 (UTC) | 数据集 | 模型 | ann | 通过 | 通过率 | 最大误差 | 耗时 均/最长 | agent | 产物 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
"""


def index_row(rec: dict) -> str:
    """把一次运行压成索引里的一行。"""
    when = str(rec.get("started_at", ""))[:16].replace("T", " ")
    ann = "含" if rec.get("with_annotations") else "不含"
    call = rec.get("call") or {}
    agent = str(call.get("agent_id") or ("--from-code" if rec.get("source") else "-"))
    if agent.startswith("bc-"):
        agent = f"`{agent[:11]}…`"

    s = rec.get("summary")
    if s is None:
        reason = str(rec.get("reason", "")).replace("|", "/")[:60]
        return (
            f"| {when} | {rec.get('problem', '?')} | {rec.get('model', '?')} | {ann} "
            f"| 运行失败 | - | - | - | {agent} | - |"
        ) + f"\n<!-- 失败原因：{reason} -->"

    insts = rec.get("instances") or []
    errs = [
        abs(e["objective"] - e["reference_objective"])
        for e in insts
        if e.get("verdict") != UNJUDGEABLE
        and e.get("objective") is not None
        and e.get("reference_objective") is not None
    ]
    err = "-" if not errs else ("0" if max(errs) == 0 else f"{max(errs):.1e}")

    secs = [e["solve_seconds"] for e in insts if e.get("solve_seconds") is not None]
    took = "-" if not secs else f"{sum(secs) / len(secs):.2f} / {max(secs):.2f} s"

    rate = "-" if s["pass_rate"] is None else f"{s['pass_rate'] * 100:.0f}%"
    link = "-"
    if rec.get("dataset_dir") and rec.get("run_dir"):
        link = f"[产物]({rec['dataset_dir']}/runs/{rec['run_dir']}/)"

    return (
        f"| {when} | {rec.get('problem', '?')} | {rec.get('model', '?')} | {ann} "
        f"| {s['passed']}/{s['judgeable']} | {rate} | {err} | {took} | {agent} | {link} |"
    )


def append_index(out_root: Path, records: list[dict]) -> Path:
    """把本次的每条记录追加进单一索引文件。

    以前是每跑一次就在 _summaries/ 下新建 summary-<时间戳>.md 和 .json 两个文件，
    每个里面只有一张单次运行的五行表。跑十几次之后目录里全是碎片，想看历史得挨个
    打开。改成一个追加式的表格，一行一次运行。
    """
    index = out_root / "runs.md"
    index.parent.mkdir(parents=True, exist_ok=True)
    if not index.exists():
        index.write_text(INDEX_HEADER, encoding="utf-8")
    with index.open("a", encoding="utf-8") as f:
        for rec in records:
            f.write(index_row(rec) + "\n")
    return index


# --------------------------------------------------------------------------
# 增量测评：靠指纹判断某次归档的结果还算不算数
#
# 滚动新增数据时不该把测过的重测一遍，但「能不能沿用旧结果」不能靠人记。分两个
# 指纹：scheme 覆盖决定判定结果的那套逻辑，dataset 覆盖喂进去的数据。两个都没变
# 才跳过，任何一个变了就重跑。
#
# 于是「测试方案变了要全量重测」这条不需要额外操作 —— 改了 prompt 模板、容差、
# 求解器路由或判定函数，scheme 指纹自动变化，所有数据集一起失配。
# --------------------------------------------------------------------------

# 判定路径上的全部函数。取源码而不是取整个文件的哈希，这样改无关的地方
# （比如日志措辞、索引格式）不会误伤已有结果。
SCHEME_FUNCS = (
    build_prompt,
    instance_dirs,
    extract_code,
    solve_generated,
    check_feasibility,
    check_against_reference,
    close,
    better_with_tolerance,
    no_worse_with_tolerance,
    load_reference,
    judge_instance,
)


def _sha(parts) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()[:12]


def scheme_fingerprint(timeout: int) -> str:
    """测试方案指纹：prompt 怎么拼、怎么求解、怎么判分。

    宁可多失效也不能漏失效 —— 一个本该重测却沿用了的 pass，比一次多余的重跑
    危险得多。所以 solve_generated 这种只影响「怎么跑」的也算进来。
    """
    parts = [
        PROMPT_TEMPLATE,
        SECTION_TEMPLATE,
        WORKER,
        f"rel_tol={REL_TOL}",
        "nonoptimal_reference_policy=judgeable_pass_if_not_worse_and_feasible",
        f"abs_tol={ABS_TOL}",
        f"timeout={timeout}",
        f"worker_mem_limit={WORKER_MEM_LIMIT}",
    ]
    parts += [inspect.getsource(fn) for fn in SCHEME_FUNCS]
    return _sha(parts)


def dataset_fingerprint(problem_dir: Path, with_annotations: bool,
                        lang: str = "zh") -> str:
    """数据指纹：模型看到的输入，加上判定要用到的参考答案。

    prompt 全文已经覆盖了 nl/ 与 data/README.md 和首个实例的样例数据（含截断规则）。
    但模型的代码要跑通全部实例，所以其余实例的数据也算进来；参考解决定目标值比对，
    参考模型决定第二层交叉验证，两者同样算。
    """
    parts = [build_prompt(problem_dir, with_annotations, lang)]
    extra = []
    for inst in instance_dirs(problem_dir):
        extra += sorted(p for p in inst.iterdir() if p.is_file())
    sol = problem_dir / "solution"
    if sol.is_dir():
        extra += sorted(p for p in sol.iterdir() if p.is_file())
    ref = problem_dir / "code" / "model.py"
    if ref.is_file():
        extra.append(ref)
    for p in extra:
        parts.append(str(p.relative_to(problem_dir)))
        parts.append(p.read_text(encoding="utf-8", errors="replace"))
    return _sha(parts)


def archived_runs(out_root: Path, dataset_dir: str):
    """按时间倒序遍历某数据集已归档的 result.json。"""
    runs = out_root / dataset_dir / "runs"
    if not runs.is_dir():
        return
    for d in sorted(runs.iterdir(), reverse=True):
        f = d / "result.json"
        if not f.is_file():
            continue
        try:
            yield d, json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue


def reuse_decision(
    out_root: Path,
    problem_dir: Path,
    model: str,
    with_annotations: bool,
    scheme_fp: str,
    dataset_fp: str,
) -> tuple[Path | None, str]:
    """能不能沿用已归档的结果。返回（可沿用的产物目录, 说明）。"""
    seen_scheme, seen_dataset = False, False
    for d, rec in archived_runs(out_root, problem_dir.name):
        if rec.get("model") != model or rec.get("with_annotations") != with_annotations:
            continue
        if rec.get("summary") is None:      # 那次没跑完，不能当依据
            continue
        fp = rec.get("fingerprint") or {}
        if fp.get("scheme") == scheme_fp and fp.get("dataset") == dataset_fp:
            return d, "方案与数据都没变"
        if fp.get("scheme") == scheme_fp:
            seen_scheme = True
        if fp.get("dataset") == dataset_fp:
            seen_dataset = True

    if seen_dataset and not seen_scheme:
        return None, "测试方案变了，需要重测"
    if seen_scheme and not seen_dataset:
        return None, "数据变了，需要重测"
    if seen_scheme or seen_dataset:
        return None, "方案与数据都变了，需要重测"
    return None, "没有可沿用的历史结果"


def print_plan(args, problems, with_ann: bool, scheme_fp: str) -> int:
    """只打印会跳过还是重测。方案一变就是全量重测，动手前值得先看一眼代价。"""
    todo, reuse_list = [], []
    for problem_dir in problems:
        if not (problem_dir / "data").is_dir():
            continue
        dataset_fp = dataset_fingerprint(problem_dir, with_ann, args.lang)
        reuse, why = reuse_decision(
            args.out, problem_dir, args.model, with_ann, scheme_fp, dataset_fp
        )
        name = str(problem_dir.relative_to(REPO_ROOT))
        n_inst = len(instance_dirs(problem_dir))
        if reuse is not None:
            reuse_list.append((name, why))
        else:
            todo.append((name, why, n_inst))

    ann = "含" if with_ann else "不含"
    print(f"\nannotations：{ann}，每个数据集跑 {args.runs} 次\n")
    if reuse_list:
        print(f"沿用历史结果（{len(reuse_list)} 个）：")
        for name, why in reuse_list:
            print(f"  {name}：{why}")
    if todo:
        print(f"\n需要重测（{len(todo)} 个）：")
        for name, why, n in todo:
            print(f"  {name}：{why}（{n} 个实例）")
        calls = len(todo) * args.runs
        print(
            f"\n合计 {calls} 次模型调用。云端单次实测 15 秒到 11 分钟，"
            f"粗估 {calls} 到 {calls * 11} 分钟。"
        )
    else:
        print("\n没有需要重测的数据集。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="端到端建模测评")
    ap.add_argument("problem_dir", nargs="?", type=Path, help="问题目录")
    ap.add_argument("--all", action="store_true", help="遍历 domains/ 下的全部数据集")
    ap.add_argument(
        "--include-examples",
        action="store_true",
        help="--all 时连 examples/ 下的参考样例一起测。默认不测：它们是演示格式用的，"
        "不是数据集本体，STATUS.md 的进度表也不统计它们",
    )
    ap.add_argument("--model", default=DEFAULT_MODEL, help=f"模型 id，默认 {DEFAULT_MODEL}")
    ap.add_argument("--runs", type=int, default=1, help="每个问题跑几次，默认 1")
    ap.add_argument(
        "--lang",
        default="zh",
        choices=("zh", "en"),
        help="题面语言。zh 用 nl/statement.md（原文），en 用 nl/statement.en.md "
        "（英文平行文本，目前只覆盖部分数据集）。语言进数据指纹，所以中英是两组"
        "独立结果，--incremental 不会互相顶掉",
    )
    ap.add_argument(
        "--no-annotations",
        action="store_true",
        help="不把 nl/annotations.md 给模型，用于测「有没有业务常识」",
    )
    ap.add_argument(
        "--from-code",
        type=Path,
        help="跳过模型调用，直接评测指定的 model.py（自测、复跑用）",
    )
    ap.add_argument(
        "--resume-dir",
        type=Path,
        help="在已有 runs/<时间戳>-.../ 目录上续跑：已有 solutions/*.json 的实例跳过求解，"
        "只补缺的实例并重写 result.json。常与 --from-code 一起用（长跑 VM 重启后）",
    )
    ap.add_argument(
        "--skip-instances",
        default="",
        help="逗号分隔的实例名（如 inst_010），跳过求解并记为不可判定/失败。"
        "不进方案指纹——只用于已知会 MemoryError 拖挂机器的特大实例",
    )
    ap.add_argument(
        "--incremental",
        action="store_true",
        help="只测没测过的。已归档结果的测试方案指纹与数据指纹都没变时跳过该数据集；"
        "方案一改则全部失配、自动全量重测",
    )
    ap.add_argument(
        "--plan",
        action="store_true",
        help="只打印每个数据集会跳过还是重测，不调模型。方案变更会导致全量重测，"
        "动手前先看一眼要花多少",
    )
    ap.add_argument(
        "--api-key-env",
        help="从哪个环境变量读 API key，默认依次尝试 CURSOR_API_KEY / CURSOR_EVAL_API_KEY / EVAL_API_KEY",
    )
    ap.add_argument("--timeout", type=int, default=DEFAULT_SOLVE_TIMEOUT, help="单实例求解超时秒数")
    ap.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "eval_reports",
        help="输出目录，默认 eval_reports/（入库归档）。只想试跑不留档就指到 eval_results/",
    )
    args = ap.parse_args()

    if args.all:
        problems = discover_problems(args.include_examples)
    elif args.problem_dir:
        problems = [args.problem_dir.resolve()]
    else:
        ap.error("给一个问题目录，或用 --all")

    if not problems:
        print("没有找到任何问题目录", file=sys.stderr)
        return 2

    if args.from_code and (len(problems) > 1 or args.runs > 1):
        ap.error("--from-code 只能配单个问题、单次运行")
    if args.resume_dir and (len(problems) > 1 or args.runs > 1):
        ap.error("--resume-dir 只能配单个问题、单次运行")
    if args.resume_dir is not None:
        args.resume_dir = args.resume_dir.resolve()
        if not args.resume_dir.is_dir():
            ap.error(f"--resume-dir 不存在：{args.resume_dir}")
        if args.from_code is None:
            cand = args.resume_dir / "generated" / "model.py"
            if cand.is_file():
                args.from_code = cand
            else:
                ap.error("--resume-dir 需要 --from-code，或目录内已有 generated/model.py")

    api_key = resolve_api_key(args.api_key_env)
    if args.from_code is None and not api_key:
        ap.error(
            "找不到 API key。三种办法：\n"
            "  1. Cloud Agent 里：在 Cursor Dashboard 的 Cloud Agents > Secrets 加一条\n"
            "     名为 CURSOR_API_KEY 的 Runtime Secret，然后重启 agent\n"
            "  2. 本机：export CURSOR_API_KEY=...（user key 从 "
            "https://cursor.com/dashboard/integrations 的 User API Keys 取，"
            "Settings > API Keys 页建的 Admin key 不认）\n"
            "  3. secret 用了别的名字：--api-key-env <变量名>\n"
            "只想评测一份现成代码、不调模型的话，用 --from-code"
        )

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    with_ann = not args.no_annotations
    records = []
    scheme_fp = scheme_fingerprint(args.timeout)
    if args.incremental or args.plan:
        print(f"测试方案指纹 {scheme_fp}（求解上限 {args.timeout}s，模型 {args.model}）")
    skipped = []

    if args.plan:
        return print_plan(args, problems, with_ann, scheme_fp)

    for problem_dir in problems:
        if not (problem_dir / "data").is_dir():
            print(f"跳过 {problem_dir}：没有 data/ 目录")
            continue

        dataset_fp = dataset_fingerprint(problem_dir, with_ann, args.lang)
        fingerprint = {"scheme": scheme_fp, "dataset": dataset_fp}

        if args.incremental and args.from_code is None:
            reuse, why = reuse_decision(
                args.out, problem_dir, args.model, with_ann, scheme_fp, dataset_fp
            )
            if reuse is not None:
                rel = reuse.relative_to(args.out)
                print(
                    f"\n=== {problem_dir.relative_to(REPO_ROOT)} · {args.model} ==="
                    f"\n  跳过：{why}，沿用 {rel}"
                )
                skipped.append((str(problem_dir.relative_to(REPO_ROOT)), why, str(rel)))
                continue
            print(f"\n（{problem_dir.relative_to(REPO_ROOT)}：{why}）")

        for run_idx in range(1, args.runs + 1):
            tag = f"run{run_idx}" if args.runs > 1 else "run1"
            print(f"\n=== {problem_dir.relative_to(REPO_ROOT)} · {args.model} · {tag} ===")
            # eval_reports/<数据集名>/runs/<时间戳>-<模型>-<ann>-<runN>/
            # 用目录名而不是 domains/... 的完整相对路径：一个数据集一个文件夹，
            # 报告 report.md 和它历次运行的产物摆在一起，翻起来方便。
            out_dir = (
                args.out
                / problem_dir.name
                / "runs"
                / f"{stamp}-{args.model}-{'with-ann' if with_ann else 'no-ann'}-{tag}"
            )
            if args.resume_dir is not None:
                out_dir = args.resume_dir
                print(f"  续跑目录 {out_dir.relative_to(REPO_ROOT)}")
            try:
                skip = {x.strip() for x in args.skip_instances.split(",") if x.strip()}
                rec = run_once(
                    problem_dir,
                    out_dir,
                    model=args.model,
                    with_annotations=with_ann,
                    from_code=args.from_code,
                    timeout=args.timeout,
                    api_key=api_key,
                    fingerprint=fingerprint,
                    resume=args.resume_dir is not None,
                    skip_instances=skip,
                    lang=args.lang,
                )
            except Exception as exc:
                rec = {
                    "problem": str(problem_dir.relative_to(REPO_ROOT)),
                    "model": args.model,
                    "with_annotations": with_ann,
                    "verdict": FAIL,
                    "reason": f"{type(exc).__name__}: {exc}",
                }
                print(f"  [错误] {rec['reason']}")
            records.append(rec)
            if rec.get("summary"):
                s = rec["summary"]
                rate = "-" if s["pass_rate"] is None else f"{s['pass_rate'] * 100:.0f}%"
                print(
                    f"  小结：{s['passed']}/{s['judgeable']} 通过（通过率 {rate}），"
                    f"{s['unjudgeable']} 个不可判定"
                )

    print(f"\n{'=' * 60}")
    if skipped:
        print(f"沿用历史结果 {len(skipped)} 个：")
        for name, why, rel in skipped:
            print(f"  {name}：{why} -> {rel}")
    if not records:
        print("没有需要重测的数据集")
        return 0
    print(format_summary(records))

    append_index(args.out, records)
    try:
        where = args.out.resolve().relative_to(REPO_ROOT)
    except ValueError:      # --out 指到仓库外面去了
        where = args.out.resolve()
    print(f"\n结果写入 {where}/")

    any_fail = any(r.get("verdict") == FAIL for r in records) or any(
        r.get("summary") and r["summary"]["passed"] < r["summary"]["judgeable"] for r in records
    )
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
