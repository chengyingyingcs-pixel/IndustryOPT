# GPT-5.6-Sol Harness 严格 No-Annotation Pass@1 重跑方案

状态：**实验已完成：19/19 问题类、146/146 实例均已评测**

实际批次 ID：`gpt-5.6-sol-high-strict-noann-pass1-rerun-20260921-100452`

原始评测批次 ID：`gpt-5.6-sol-high-strict-noann-pass1-rerun-20260921-100452-timeout7200-sequential-mem32-betterref-fresh-20260922-060813`

最终重判批次 ID：`gpt-5.6-sol-high-strict-noann-pass1-rerun-20260921-100452-timeout7200-sequential-mem32-betterref-rejudge-notworse-20260926-083558`

首次评测目录 `gpt-5.6-sol-high-strict-noann-pass1-rerun-20260921-100452-timeout7200-sequential`
因未显式传递 `--model` 和 `--no-annotations`，结果元数据被评测器默认标为
`composer-2.5`/含 annotations；该运行在第 5 类开始时中止，目录保留但整体作废，不进入统计。

第二次评测目录
`gpt-5.6-sol-high-strict-noann-pass1-rerun-20260921-100452-timeout7200-sequential-corrected-metadata`
使用正确元数据，但仅完成 9 类；本次 32 GiB 评测从新的空目录启动，不续跑或复用该目录中的解。

第三次评测目录
`gpt-5.6-sol-high-strict-noann-pass1-rerun-20260921-100452-timeout7200-sequential-mem32-fresh-20260922-030623`
使用 32 GiB 限制并从零开始，但在第 10 类运行时因新增“优于非最优参考即可通过”的判据而中止；
目录保留但不与新判据结果混合统计。

原始评测器快照 SHA-256：`636a675e016c7dcaf2c3ac2fe0f9945bef1782d0d69c4a2d9ba2b8db86071719`

最终重判评测器 SHA-256：`d450a4c287804489e4a11da427c91e179bc6ffe76e63373be54839f8bcd77a0d`

最终重判方案指纹：`1939da46299a`

本文档记录重跑实验的设置、输入边界、生成提示词、结果归档方式和最终结果。生成阶段与求解阶段均已完成；旧批次仅作审计留档，不纳入最终统计。

## 1. 实验目标

在当前 IndustryOPT 数据集版本上，复现报告中 `gpt-5.6-sol`、`reasoning_effort=high` 的严格 no-annotation 条件：

- 每个问题类生成 1 份通用候选 `model.py`；
- 不向模型提供 `nl/annotations.md`；
- 将同一份候选代码用于该问题类的全部实例；
- 按 `pass@1` 的问题类级候选、实例级判定口径统计结果；
- 生成和求解分阶段归档，保留提示词、输入清单、工具事件、候选代码、生成日志、求解日志和 `result.json`。

本次重跑不复用已有 no-ann 候选代码，也不把已有 no-ann 结果当作重跑结果。

## 2. 数据与运行环境

| 项目 | 实际设置 |
| --- | --- |
| 数据集根目录 | `/public/chengyingying/project/industry_mathopt_dataset` |
| 问题目录 | `domains/<问题类>/` |
| 问题类数量 | 当前 `domains/` 下的 19 个目录 |
| 实例数量 | 当前版本实际 146 个实例，已完成启动前清单校验 |
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
| 内存限制 | 32 GB 地址空间（按评测器实现） |
| MIP gap | 相对和绝对 gap 均为 `1e-6` |
| 求解器顺序 | LP/MILP: `appsi_highs` -> `scip`；整数非线性: `scip` -> `couenne`；连续 QP/NLP: `ipopt` -> `couenne` |

实际运行使用当前数据集评测器的批次专用快照
`/home/chengyingying/IndustryOPT/tools/run_eval_gpt56_noann_rerun.py`。原因是数据集工作树中的
`tools/eval/run_eval.py` 已有未提交的 SCIP-only 修改；为不覆盖该修改且保持本方案的
`appsi_highs -> scip` 顺序，快照保留当前实现的 HiGHS 单线程和显式时限修复，只将线性
模型的求解器顺序恢复为本表配置。启动评测前记录快照 SHA-256。

### 2.1 生成模型的显式指定

`/home/chengyingying/.codex/config.toml` 的默认模型为 `gpt-5.6-sol`，且
`tools/run_codex_harness.py` 已在 `codex exec` 中显式指定该模型。每个生成会话实际使用的是：

```text
--model gpt-5.6-sol
-c model_reasoning_effort="high"
```

实验中已记录 `codex --version`、最终命令、模型配置和提示词 SHA-256；模型参数均在 CLI 层得到确认。

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

Codex 当前工作目录指向上述独立 `workspace/`，其父目录不包含数据集仓库。准备工作区时只从数据集目录读取允许的源文件，并已完成以下检查：

- `realpath(workspace)` 不以数据集根目录为前缀，数据集根目录也不以工作区为前缀；
- 工作区内没有指向数据集的符号链接、硬链接或 bind mount；
- 工作区清单只包含本节列出的文件；
- Codex 启动命令的 `-C`、当前进程工作目录和 `--output-last-message` 路径均不指向数据集源目录。

提示词要求模型不读取父目录、绝对路径、环境变量、网络资源、隐藏参考模型和参考解，也不修改输入文件。由于本次运行使用 `danger-full-access` 以保证 Codex CLI 可执行，以上是目录和输入材料隔离，不是操作系统层面的硬沙箱；已保留 `events.jsonl`，并在本报告中如实说明这一边界。若要提供更强的隔离，应改用能限制工作区外读取的 sandbox。

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
3. 使用 7200 秒单求解器时限、既定求解器轮换、32 GB 内存上限和 `1e-6` gap。
4. 保存每个实例的构建、求解、可行性、交叉验证、目标比较和最终 `pass`/`fail`/`unjudgeable` 记录。
5. 生成独立的汇总脚本或人工复核，确认实例总数、参考状态分母和问题类级候选数与本方案一致。

## 3. 判定与统计口径

参考解 `status == optimal` 时，候选模型需要：

1. 成功构建并由适用求解器返回可用解；
2. 通过候选模型自身的变量域、约束和目标一致性检查；
3. 在变量空间兼容时通过参考模型双向交叉检查；交叉检查因变量族不一致而 abstain 不直接判失败；
4. 候选目标与参考最优目标满足：

```text
abs(candidate - reference) <= max(1e-6, 1e-6 * max(abs(candidate), abs(reference)))
```

参考解不是 `optimal` 时，实例仍进入可判定分母。候选须成功求解、通过自身可行性检查，且
参考模型交叉检查不能判定违反；候选与参考模型的目标方向还必须一致。在此基础上，候选目标
严格优于参考目标，或与参考目标处于上述 `1e-6` 绝对/相对容差内（视为相等），则该实例记为
`pass`。严格优于时标记 `passed_by_better_than_nonoptimal_reference: true`；相等时该标记为
`false`。候选目标劣于参考、目标方向不一致或缺少必要比较信息时记为失败或不可判定。

对于 `optimal` 参考，超时、内存错误、模型不可行、目标不匹配或候选代码错误记为失败。

本次结果至少报告：总实例数、参考最优实例数、扩展口径可判定实例数、通过、失败、不可判定、
其中因优于非最优参考而通过的数量、标准 `optimal` 参考口径通过率和扩展口径通过率。
问题类表格按“通过/可判定”列出，不将同一问题类的多个实例误报为多个 completion。

## 4. 结果归档

本次使用了明确包含模型和条件的独立 batch ID：

```text
gpt-5.6-sol-high-strict-noann-rerun-pass1-<UTC_TIMESTAMP>
```

实际归档目录（与 Codex 工作区分离）：

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
执行本地校验命令；脚本实现与本报告中的隔离边界一致。

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

启动时已检查 generation batch 不存在同名旧结果；旧目录未被覆盖。

## 5. 生成建模代码的提示词

以下文本按逐问题类原样传给 `codex exec`。no-ann 条件通过只提供 `statement.md` 和 `data_README.md` 实现；工作区中没有 annotations、实例样例或本地校验器。

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

## 6. 实验复核清单

- [x] 确认使用当前数据集版本，并记录 19 个问题类和 146 个实例的实际清单。
- [x] 确认生成模型为 `gpt-5.6-sol`，且脚本通过 `--model` 显式指定。
- [x] 确认 `reasoning_effort=high` 已实际传入生成会话。
- [x] 确认 no-ann 工作区不存在 `annotations.md`。
- [x] 确认最终求解批次从新的空目录启动；中断后仅在同一批次内复用已落盘解续跑。
- [x] 确认生成阶段与求解阶段分开启动。
- [x] 确认 Codex workspace 位于数据集目录之外，且不存在指向数据集的链接或挂载。
- [x] 确认 `realpath`、工作区文件清单和 `-C` 路径检查通过。
- [x] 确认 32 GiB 地址空间限制、7200 秒单求解器时限和评测器快照指纹均已记录。

## 7. 最终结果

最终重判批次为：

```text
/public/chengyingying/project/industry_mathopt_dataset/eval_results/harness_sweep/evals/
gpt-5.6-sol-high-strict-noann-pass1-rerun-20260921-100452-timeout7200-sequential-mem32-betterref-rejudge-notworse-20260926-083558/
```

重判于 `2026-09-26T08:48Z` 左右完成，最终生成 19 份 `result.json`。重判只复用原始批次已落盘的解文件；缺少缓存解的失败实例重新执行了相同的建模/求解步骤。汇总如下：

| 指标 | 数量 | 比例 |
| --- | ---: | ---: |
| 总实例 | 146 | 100% |
| 参考解为 `optimal` | 131 | 89.73% |
| 参考解非最优 | 15 | 10.27% |
| 可判定实例 | 146 | 100% |
| 通过 | 107 | 73.29% / 总实例；73.29% / 可判定实例 |
| 失败 | 39 | 26.71% / 可判定实例 |
| 不可判定 | 0 | 0% |
| 因严格优于非最优参考而通过 | 9 | 已计入 107 个通过 |

按标准 `optimal` 参考解口径，97/131 个实例通过，通过率为 **74.05%**。新口径将 15 个非最优参考实例全部纳入可判定集合，其中 10 个通过（9 个严格更优、1 个容差内相等），最终得到 107/146 个可判定实例通过，即 **73.29%**。

问题类级明细如下；分子为通过实例数，分母为可判定实例数，括号内为该类全部实例数：

| 问题类 | 通过/可判定 | 全部实例 |
| --- | ---: | ---: |
| Auto-Vehicle-ActiveSuspensionBalance | 0/8 | 8 |
| CBG-Camera-JPEGQuantizationTable | 8/8 | 8 |
| CBG-Camera-VideoStabilization-L1 | 8/8 | 8 |
| CBG-Camera-VideoStabilization-L2 | 6/8 | 8 |
| CBG-Communication-RailCellHandover | 5/5 | 5 |
| CBG-HarmonyOS-CriticalThreadOpt | 5/5 | 5 |
| CBG-HarmonyOS-MemoryEviction | 8/8 | 8 |
| Compute-CAE-SparseLA-LDLSymmetricPivoting | 0/6 | 6 |
| Compute-CAE-SparseLA-LUPivotReordering | 0/6 | 6 |
| Compute-Cluster-CrossPodLoadBalancing | 8/10 | 10 |
| Compute-LLM-MoEExpertLoadBalance | 3/5 | 5 |
| Compute-TBE-MemoryAllocation | 2/8 | 8 |
| Energy-Microgrid-SizingAndOperation | 4/10 | 10 |
| Energy-VPP-DayAheadAdjustableLoadScheduling | 15/15 | 15 |
| ICT-DataCom-LoadBalancing-SingleAndMultitimestamp | 8/8 | 8 |
| ICT-DataCom-NetworkPlanning-CapacityExpansion | 8/8 | 8 |
| ICT-OpticalNetwork-NetworkPlanning-LinkProtection | 4/5 | 5 |
| ICT-OpticalNetwork-NetworkPlanning-PathProtection | 5/5 | 5 |
| ICT-Wireless-ChannelEstimation-SparseDelay | 10/10 | 10 |

本次最终统计使用的重判评测器 SHA-256 为
`d450a4c287804489e4a11da427c91e179bc6ffe76e63373be54839f8bcd77a0d`，方案指纹为
`1939da46299a`。重判结果目录中的 `runs.md`、各问题类 `result.json`、实例日志和解文件构成完整审计记录；原始批次仍保留供对照。

## 8. 失败与不可判定实例分析

按新口径，最终 39 个失败实例和 0 个不可判定实例均已纳入可判定集合。15 个参考解非最优的
实例不再自动标记为不可判定：候选可行且目标不劣于参考（严格更优或容差内相等）即通过，候选
劣于参考即失败。失败不是由评测批次中断、内存上限或求解器未安装造成：32 GiB 地址空间限制
有效，日志中没有 OOM；失败原因都记录在对应问题类的 `result.json` 和实例日志中。

### 8.1 失败实例

| 原因 | 数量 | 问题类/实例 | 证据与判断 |
| --- | ---: | --- | --- |
| 最优参考目标值不匹配 | 21 | `Auto-Vehicle-ActiveSuspensionBalance` 8；`CBG-Camera-VideoStabilization-L2` 1（`inst_003`）；`Compute-LLM-MoEExpertLoadBalance` 1（`inst_004`）；`Compute-TBE-MemoryAllocation` 4（`inst_001`、`003`、`004`、`005`）；`Energy-Microgrid-SizingAndOperation` 6（`inst_001`--`006`）；`ICT-OpticalNetwork-NetworkPlanning-LinkProtection` 1（`inst_003`） | 候选模型自身可行并返回解，但目标值不满足与 `optimal` 参考解的 `1e-6` 绝对/相对容差。除 MoE `inst_004` 达到 `maxTimeLimit` 外，其余均报告最优或正常终止。Energy-Microgrid 中候选值看似低于参考值，但参考解已标为 `optimal`，且变量命名不同导致参考模型交叉验证 abstain；因此按最优参考规则仍判失败。总体上反映目标函数、约束语义或单位/缩放与参考模型不一致。 |
| 候选代码无法解析实例输入 | 12 | `Compute-CAE-SparseLA-LDLSymmetricPivoting` 6；`Compute-CAE-SparseLA-LUPivotReordering` 6 | 两个问题类的实例目录实际包含 `data.json` 和原始 Matrix Market `.mtx` 文件。生成代码分别报 `KeyError: 'matrix data not found'` 和 `ValueError: could not find Matrix Market payload in data`，在 `build()` 阶段退出，求解器未启动。根因是代码假定矩阵内容已经以某种 payload 形式出现在 `data` 字典中，没有按 `matrix_path`/实例文件读取或兼容评测器的数据表示。 |
| 候选模型不可行 | 1 | `CBG-Camera-VideoStabilization-L2/inst_004` | IPOPT 返回 “local infeasibility”，Couenne 也报告 `Problem infeasible`，因此没有候选目标值。参考解为 `optimal`，属于候选模型约束或数据解释错误，而不是参考解不可判定。 |
| 非最优参考下候选目标更差 | 5 | `Compute-Cluster-CrossPodLoadBalancing` `inst_005`、`inst_006`；`Compute-LLM-MoEExpertLoadBalance` `inst_005`；`Compute-TBE-MemoryAllocation` `inst_006`、`inst_007` | 这些实例的参考状态为 `feasible` 或 `heuristic`，但候选已通过可行性检查且目标劣于参考。按新口径，非最优参考不再导致不可判定；候选更差因此明确判失败。 |

目标不匹配的失败实例中，候选通常能通过自身可行性检查，但参考模型交叉检查因变量命名/变量族不同而 abstain；这只能说明候选模型内部自洽，不能证明它实现了题目要求。尤其是候选目标显著偏离参考值的 ActiveSuspension，以及固定成组偏离的 TBE/Microgrid，优先怀疑漏约束、目标项遗漏、单位换算或输入字段解释错误，而不是求解器精度问题。

### 8.2 非最优参考实例的重判

15 个非最优参考实例全部可比较、全部进入分母：

- 通过 10 个：CrossPod 5 个（其中 `inst_003` 与参考在容差内相等，另外 4 个严格更优）、TBE 1 个、Microgrid 4 个。
- 失败 5 个：CrossPod 2 个、MoE 1 个、TBE 2 个，均因候选目标劣于参考。
- 不可判定 0 个。

因此，原报告中“参考解非最优即不可判定”的归类已废止；最终报告只保留新口径结果。

### 8.3 结论与改进方向

主要质量瓶颈集中在三种能力：从 `data.json` 与原始文件建立稳健输入适配、完整还原目标/约束语义、以及在无 annotations 条件下处理大规模/复杂非线性模型。下一轮改进应优先针对 CAE 两类的文件读取契约、ActiveSuspension 的目标与单位定义、Camera-L2 的可行性约束，以及 TBE/Microgrid 的目标项和容量约束进行定向复核；新口径只改变非最优参考实例的统计归类，不通过放宽最优参考的目标容差来掩盖模型语义差异。
