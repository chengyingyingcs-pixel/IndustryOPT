# GPT-5.6-Sol Harness 严格 No-Annotation Pass@1 重跑方案

状态：**19/19 候选已生成，全量评测运行中**

实际批次 ID：`gpt-5.6-sol-high-strict-noann-pass1-rerun-20260921-100452`

实际评测批次 ID：`gpt-5.6-sol-high-strict-noann-pass1-rerun-20260921-100452-timeout7200-sequential-corrected-metadata`

首次评测目录 `gpt-5.6-sol-high-strict-noann-pass1-rerun-20260921-100452-timeout7200-sequential`
因未显式传递 `--model` 和 `--no-annotations`，结果元数据被评测器默认标为
`composer-2.5`/含 annotations；该运行在第 5 类开始时中止，目录保留但整体作废，不进入统计。

评测器快照 SHA-256：`4d3d76076b72755d9dd5310e28c891a7c1821612a98811c88decd8afac5e05ab`

本文档用于确认重跑实验的设置、输入边界、生成提示词和结果归档方式。获得确认前，不启动模型生成或全量求解。

## 1. 实验目标

在当前 IndustryOPT 数据集版本上，复现报告中 `gpt-5.6-sol`、`reasoning_effort=high` 的严格 no-annotation 条件：

- 每个问题类生成 1 份通用候选 `model.py`；
- 不向模型提供 `nl/annotations.md`；
- 将同一份候选代码用于该问题类的全部实例；
- 按 `pass@1` 的问题类级候选、实例级判定口径统计结果；
- 生成和求解分阶段归档，保留提示词、输入清单、工具事件、候选代码、生成日志、求解日志和 `result.json`。

本次重跑不复用已有 no-ann 候选代码，也不把已有 no-ann 结果当作重跑结果。

## 2. 数据与运行环境

| 项目 | 拟采用设置 |
| --- | --- |
| 数据集根目录 | `/public/chengyingying/project/industry_mathopt_dataset` |
| 问题目录 | `domains/<问题类>/` |
| 问题类数量 | 当前 `domains/` 下的 19 个目录 |
| 实例数量 | 当前版本预计 146 个实例，以启动前清单校验为准 |
| 模型 | `gpt-5.6-sol` |
| 推理强度 | `high` |
| 生成条件 | strict no-annotation；不复制 `nl/annotations.md` |
| 生成采样 | 每类 1 次，即问题类级 `pass@1` |
| 建模接口 | `build(data) -> pyomo.environ.ConcreteModel` |
| Python | `/public/chengyingying/conda_envs/inferopt-py311/bin/python` |
| 本地校验器 | 不提供、不运行 `validate_model.py` |
| 求解阶段 | 使用当前数据集评测器派生的批次专用快照 |
| 单求解器时限 | 7200 秒 |
| 实例级保护时限 | 由评测器按 `7200 * 3 + 60` 秒执行 |
| 内存限制 | 10 GB 地址空间（按评测器实现） |
| MIP gap | 相对和绝对 gap 均为 `1e-6` |
| 求解器顺序 | LP/MILP: `appsi_highs` -> `scip`；整数非线性: `scip` -> `couenne`；连续 QP/NLP: `ipopt` -> `couenne` |

实际运行使用当前数据集评测器的批次专用快照
`/home/chengyingying/IndustryOPT/tools/run_eval_gpt56_noann_rerun.py`。原因是数据集工作树中的
`tools/eval/run_eval.py` 已有未提交的 SCIP-only 修改；为不覆盖该修改且保持本方案的
`appsi_highs -> scip` 顺序，快照保留当前实现的 HiGHS 单线程和显式时限修复，只将线性
模型的求解器顺序恢复为本表配置。启动评测前记录快照 SHA-256。

### 2.1 生成模型的显式指定

`/home/chengyingying/.codex/config.toml` 的默认模型为 `gpt-5.6-sol`，且
`tools/run_codex_harness.py` 已在 `codex exec` 中显式指定该模型。正式启动前仍需检查每个
生成会话实际使用的是：

```text
--model gpt-5.6-sol
-c model_reasoning_effort="high"
```

在启动前应记录 `codex --version`、最终命令、模型配置和提示词 SHA-256；若模型参数无法在 CLI 层得到确认，则暂停启动，不将默认配置推断为实际配置。

### 2.2 输入材料与隔离边界

每个问题类单独建立工作区。**工作区根目录必须位于数据集目录之外，二者不能互为父子目录，也不能通过软链接相连**：

```text
数据集（只作为复制源）：
/public/chengyingying/project/industry_mathopt_dataset/

Codex 工作区（独立目录）：
/public/chengyingying/project/industryopt_harness_workspaces/<BATCH_ID>/<问题类>/workspace/
```

每个工作区只复制以下材料：

```text
statement.md       <- domains/<问题类>/nl/statement.md
data_README.md     <- domains/<问题类>/data/README.md
```

有意不复制：

- `nl/annotations.md`；
- `sample_data/` 或任何实例数据；
- `validate_model.py` 或其他本地校验器；
- `formulation/model.md`；
- `code/model.py`；
- `solution/*.json`；
- 其他实例数据；
- 原始仓库工作目录。

Codex 当前工作目录指向上述独立 `workspace/`，其父目录不包含数据集仓库。准备工作区时只从数据集目录读取允许的源文件，并在启动前检查：

- `realpath(workspace)` 不以数据集根目录为前缀，数据集根目录也不以工作区为前缀；
- 工作区内没有指向数据集的符号链接、硬链接或 bind mount；
- 工作区清单只包含本节列出的文件；
- Codex 启动命令的 `-C`、当前进程工作目录和 `--output-last-message` 路径均不指向数据集源目录。

提示词要求模型不读取父目录、绝对路径、环境变量、网络资源、隐藏参考模型和参考解，也不修改输入文件。由于本次运行计划使用 `danger-full-access` 以保证 Codex CLI 可执行，以上是目录和输入材料隔离，不是操作系统层面的硬沙箱；应保留 `events.jsonl`，并在实验报告中如实说明这一边界。若要提供更强的隔离，应改用能限制工作区外读取的 sandbox，并在启动前先完成同样的路径检查。

### 2.3 生成阶段流程

1. 在独立工作区根目录和结果归档根目录分别创建新的、带时间戳的 batch 目录；两者均不得复用旧目录。
2. 从数据集目录只复制 `statement.md` 和 `data_README.md` 到独立工作区；审计用的 `input_inventory.json`、`prompt.txt` 和 `prompt.sha256` 写在 workspace 外层的 staging 目录，不作为模型输入。
3. 对每个问题类调用一次 `codex exec`，允许模型在当前工作区内读取这两个输入文件并修改 `model.py`；不提供本地样例数据或校验器。
4. 生成结束后仅检查 `model.py` 是否生成，并保存 Codex stdout、stderr、返回码和耗时；不执行 `validate_model.py`。
5. 将生成的 `model.py` 复制为 generation 目录下的候选归档；缺失候选的记录必须保留，不能静默跳过。

### 2.4 求解阶段流程

生成阶段全部结束并完成检查后，再启动全量评测：

1. 使用每个问题类归档的候选 `model.py`，不重新调用模型。
2. 通过 `run_eval.py --from-code` 加载每个问题类的全部实例。
3. 使用 7200 秒单求解器时限、既定求解器轮换、10 GB 内存上限和 `1e-6` gap。
4. 保存每个实例的构建、求解、可行性、交叉验证、目标比较和最终 `pass`/`fail`/`unjudgeable` 记录。
5. 生成独立的汇总脚本或人工复核，确认实例总数、参考状态分母和问题类级候选数与本方案一致。

## 3. 判定与统计口径

只有参考解 `status == optimal` 的实例进入 `pass@1` 分母。候选模型需要：

1. 成功构建并由适用求解器返回可用解；
2. 通过候选模型自身的变量域、约束和目标一致性检查；
3. 在变量空间兼容时通过参考模型双向交叉检查；交叉检查因变量族不一致而 abstain 不直接判失败；
4. 候选目标与参考最优目标满足：

```text
abs(candidate - reference) <= max(1e-6, 1e-6 * max(abs(candidate), abs(reference)))
```

参考解不是 `optimal` 的实例记为 `unjudgeable`，不计入准确率分母；超时、内存错误、模型不可行、目标不匹配或候选代码错误的可判定实例记为失败。

本次结果至少报告：总实例数、可判定实例数、通过、失败、不可判定、`pass@1`（可判定分母）和全部参考最优实例上的保守通过比例。问题类表格按“通过/可判定”列出，不将同一问题类的多个实例误报为多个 completion。

## 4. 结果归档建议

建议使用新的、明确包含模型和条件的 batch ID，例如：

```text
gpt-5.6-sol-high-strict-noann-rerun-pass1-<UTC_TIMESTAMP>
```

拟归档目录（与 Codex 工作区分离）：

```text
/public/chengyingying/project/industry_mathopt_dataset/eval_results/harness_sweep/
  generations/<BATCH_ID>/
  evals/<BATCH_ID>-timeout7200-sequential/
```

Codex 实际工作区不放在上述 `eval_results/` 下，而放在：

```text
/public/chengyingying/project/industryopt_harness_workspaces/<BATCH_ID>/
```

`tools/run_codex_harness.py` 的 `run_generation()` 已将 workspace 根目录改为上述独立路径，
并让 `prepare_workspace()`、`codex exec -C` 和候选代码复制都使用该路径。no-ann 生成阶段不
执行本地校验命令；正式启动前仍需检查脚本实现与本报告一致，不能只在报告中声明隔离。

每个问题类至少保留（其中前三项位于 workspace 外层 staging 目录）：

```text
prompt.txt
prompt.sha256
input_inventory.json
events.jsonl
response.md
codex_stderr.log
record.json 中的候选生成状态（本条件不执行本地校验器）
model.py
eval_stdout.log
eval_stderr.log
```

启动前应再次检查 generation batch 不存在同名旧结果；若目录已存在，应换用新的 batch ID，而不是覆盖已有实验。

## 5. 生成建模代码的提示词

以下文本拟逐问题类原样传给 `codex exec`。no-ann 条件通过只提供 `statement.md` 和 `data_README.md` 实现；工作区中没有 annotations、实例样例或本地校验器。

```text
You are being evaluated as a Codex modeling harness.

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
```

## 6. 启动前复核清单

- [ ] 确认使用当前数据集版本，并记录 19 个问题类和 146 个实例的实际清单。
- [ ] 确认生成模型为 `gpt-5.6-sol`，且脚本通过 `--model` 显式指定。
- [ ] 确认 `reasoning_effort=high` 已实际传入每个会话。
- [ ] 确认 no-ann 工作区不存在 `annotations.md`。
- [ ] 确认不复用已有 no-ann generation/eval 目录。
- [ ] 确认生成阶段与求解阶段分开启动。
- [ ] 确认 Codex workspace 位于 `/public/chengyingying/project/industry_mathopt_dataset/` 之外，且不存在指向数据集的链接或挂载。
- [ ] 确认 `realpath`、工作区文件清单和 `-C` 路径检查均通过。
- [ ] 确认实验开始前由用户 review 本文档并批准启动。
